# --- START OF FINAL CORRECTED FILE: cogops/utils/token_manager.py ---

import logging
from transformers import AutoTokenizer
from typing import List, Tuple, Dict, Any, Union

class TokenManager:
    """
    A utility class for managing token counts and truncating prompts to fit
    within a model's context window.
    """
    def __init__(self, model_name: str, reservation_tokens: int, history_budget: float):
        """
        Initializes the tokenizer and configuration for prompt building.
        """
        logging.info(f"Initializing TokenManager with tokenizer from '{model_name}'...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.reservation_tokens = reservation_tokens
            self.history_budget = history_budget
            logging.info(f"✅ TokenManager initialized. Reservation: {reservation_tokens} tokens, History Budget: {history_budget*100}%.")
        except Exception as e:
            logging.critical(f"FATAL: Could not initialize tokenizer for '{model_name}'. Error: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """Counts the number of tokens in a given string."""
        if not text:
            return 0
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def _truncate_history(self, history: List[Tuple[str, str]], max_tokens: int) -> str:
        """
        Truncates conversation history from oldest to newest to fit the token budget.
        Returns a formatted string of the truncated history.
        """
        if not history:
            return "No conversation history yet."
            
        truncated_history = list(history)
        while truncated_history:
            # The format here MUST match the one expected in the prompt
            formatted_history = "\n---\n".join([f"User: {u}\nAssistant: {a}" for u, a in truncated_history])
            if self.count_tokens(formatted_history) <= max_tokens:
                if len(truncated_history) < len(history):
                    logging.warning(f"History truncated from {len(history)} to {len(truncated_history)} turns to fit token budget.")
                return formatted_history
            truncated_history.pop(0) # Remove the oldest turn
        
        logging.warning("History is too long to be included in this turn's context, even after truncation.")
        return "History is too long to be included in this turn's context."

    def build_safe_prompt(self, template: str, max_tokens: int, **kwargs: Any) -> str:
        """
        Builds a prompt from a template and its components, ensuring it does not
        exceed the maximum token limit through intelligent truncation of dynamic content.
        """
        available_content_tokens = max_tokens - self.reservation_tokens

        tokens_used = 0
        final_components = {}
        
        for key, value in kwargs.items():
            # Exclude keys for dynamic, truncatable content from the initial token count.
            if key not in ['history']:
                str_value = str(value)
                final_components[key] = str_value
                tokens_used += self.count_tokens(str_value)
        
        remaining_tokens = available_content_tokens - tokens_used
        if remaining_tokens < 0:
            logging.error(f"Static components alone ({tokens_used} tokens) exceed the available budget. Prompt will be severely truncated.")
            remaining_tokens = 0

        history_str = "No conversation history yet."
        if 'history' in kwargs and kwargs['history']:
            history_budget_tokens = int(remaining_tokens * self.history_budget)
            history_str = self._truncate_history(kwargs['history'], history_budget_tokens)
        
        # --- CRITICAL FIX REVERTED AND CORRECTED ---
        # My previous correction was an error. After reviewing your `prompt.py`, the placeholder
        # is indeed `{conversation_history}`. This restores the correct key.
        final_components['conversation_history'] = history_str
        # We no longer need the incorrect 'history' key.
        if 'history' in final_components:
            del final_components['history']
        # --- END OF FIX ---
        
        try:
            # We now must provide a value for the `{history}` placeholder that was in the kwargs,
            # even though it's not in the final prompt template. The .format method requires it.
            # We pass an empty string for any keys that were in kwargs but not in the final dict.
            # A cleaner way is to ensure all kwargs keys are present. Let's do that.
            # Add back the original history from kwargs to satisfy the formatter.
            final_components['history'] = kwargs.get('history', [])

            final_prompt = template.format(**final_components)
        except KeyError as e:
            # This logic is now more robust.
            # Let's ensure all expected keys from the prompt template are present.
            # Forcing a default for `conversation_history` if not set.
            final_components.setdefault('conversation_history', "No conversation history yet.")
            final_prompt = template.format(**{k: v for k, v in final_components.items() if f"{{{k}}}" in template})
            logging.warning(f"A minor key mismatch was handled during prompt formatting. Missing key was likely: {e}")

        total_tokens = self.count_tokens(final_prompt)
        if total_tokens > max_tokens:
            logging.warning(f"Prompt exceeded budget after final assembly ({total_tokens}/{max_tokens}). Performing hard truncation.")
            encoded_prompt = self.tokenizer.encode(final_prompt)
            truncated_encoded = encoded_prompt[:max_tokens]
            final_prompt = self.tokenizer.decode(truncated_encoded, skip_special_tokens=True)
            
        return final_prompt

# --- END OF FINAL CORRECTED FILE: cogops/utils/token_manager.py ---