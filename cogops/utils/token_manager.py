# FILE: cogops/utils/token_manager.py

import logging
from transformers import AutoTokenizer
from typing import List, Tuple, Dict, Any, Union
from pydantic import BaseModel

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
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.reservation_tokens = reservation_tokens
        self.history_budget = history_budget
        logging.info(f"✅ TokenManager initialized. Reservation: {reservation_tokens} tokens, History Budget: {history_budget*100}%.")

    def count_tokens(self, text: str) -> int:
        """Counts the number of tokens in a given string."""
        if not text:
            return 0
        return len(self.tokenizer.encode(text))

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
                return formatted_history
            truncated_history.pop(0)
        
        return "History is too long to be included in this turn's context."

    def _truncate_passages(self, passages: Union[List[Any], str], max_tokens: int) -> str:
        # ... (This function remains unchanged from your provided file) ...
        pass

    def build_safe_prompt(self, template: str, max_tokens: int, **kwargs: Dict[str, Any]) -> str:
        """
        Builds a prompt from a template and components, ensuring it does not
        exceed the maximum token limit through intelligent truncation.
        """
        available_content_tokens = max_tokens - self.reservation_tokens

        tokens_used = 0
        final_components = {}
        # First, process all non-truncatable components
        for key, value in kwargs.items():
            if key not in ['history', 'passages_context']: # 'passages_context' is an example key
                str_value = str(value)
                final_components[key] = str_value
                tokens_used += self.count_tokens(str_value)
        
        remaining_tokens = available_content_tokens - tokens_used
        if remaining_tokens < 0:
            logging.warning("Fixed components alone exceed token budget. Prompt will be truncated.")
            remaining_tokens = 0

        history_str = ""
        # Process history with its budget
        if 'history' in kwargs and kwargs['history']:
            history_budget_tokens = int(remaining_tokens * self.history_budget)
            history_str = self._truncate_history(kwargs['history'], history_budget_tokens)
            tokens_used += self.count_tokens(history_str)
        
        # --- START OF FIX ---
        # The key here MUST match the placeholder in the AGENT_PROMPT string.
        final_components['conversation_history'] = history_str
        # --- END OF FIX ---

        # You can add similar logic for other dynamic, truncatable contexts here
        # For example, if you had a 'documents' context:
        # passage_tokens_budget = available_content_tokens - tokens_used
        # passage_str = self._truncate_passages(kwargs.get('passages_context'), passage_tokens_budget)
        # final_components['passages_context'] = passage_str

        # Finally, format the template with the assembled components.
        final_prompt = template.format(**final_components)
        
        # A final safety check in case formatting added extra tokens
        if self.count_tokens(final_prompt) > max_tokens:
            encoded_prompt = self.tokenizer.encode(final_prompt)
            truncated_encoded = encoded_prompt[:max_tokens]
            final_prompt = self.tokenizer.decode(truncated_encoded, skip_special_tokens=True)
            logging.warning("Prompt exceeded budget after final assembly and was hard-truncated.")
            
        return final_prompt