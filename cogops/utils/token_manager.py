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
            formatted_history = "\n---\n".join([f"User: {u}\nAI: {a}" for u, a in truncated_history])
            if self.count_tokens(formatted_history) <= max_tokens:
                return formatted_history
            truncated_history.pop(0)
        
        return "History is too long to be included."

    def _truncate_passages(self, passages: Union[List[Any], str], max_tokens: int) -> str:
        """
        Truncates passages to fit the token budget. Handles both a list of passage
        objects/dicts and a single pre-formatted string of context.
        """
        if not passages:
            return ""

        # --- NEW: Handle the case where a single string (from web search) is passed ---
        if isinstance(passages, str):
            if self.count_tokens(passages) <= max_tokens:
                return passages
            else:
                # If the string is too long, truncate it by tokens
                encoded_prompt = self.tokenizer.encode(passages)
                truncated_encoded = encoded_prompt[:max_tokens]
                logging.warning(f"Web passages context was too long and has been truncated to {max_tokens} tokens.")
                return self.tokenizer.decode(truncated_encoded, skip_special_tokens=True)
        # --- END NEW ---

        # Original logic for handling a list of passages
        if isinstance(passages, list):
            for i in range(len(passages), 0, -1):
                current_passages = passages[:i]
                
                formatted_passages = []
                for p in current_passages:
                    if isinstance(p, BaseModel):
                        passage_id = p.passage_id
                        document = p.document
                    else:
                        passage_id = p.get('metadata', {}).get('passage_id', p.get('id', 'N/A'))
                        document = p.get('document', '')
                    
                    formatted_passages.append(f"Passage ID: {passage_id}\nContent: {document}")

                context = "\n\n".join(formatted_passages)

                if self.count_tokens(context) <= max_tokens:
                    return context
        
        return "" # Fallback for empty or unhandled types

    def build_safe_prompt(self, template: str, max_tokens: int, **kwargs: Dict[str, Any]) -> str:
        """
        Builds a prompt from a template and components, ensuring it does not
        exceed the maximum token limit through intelligent truncation.
        """
        available_content_tokens = max_tokens - self.reservation_tokens

        tokens_used = 0
        final_components = {}
        for key, value in kwargs.items():
            if key not in ['history', 'passages_context']:
                str_value = str(value)
                final_components[key] = str_value
                tokens_used += self.count_tokens(str_value)
        
        remaining_tokens = available_content_tokens - tokens_used
        if remaining_tokens < 0:
            logging.warning("Fixed components alone exceed token budget. Prompt will be truncated.")
            remaining_tokens = 0

        history_str = ""
        passage_str = ""

        if 'history' in kwargs and kwargs['history']:
            history_budget_tokens = int(remaining_tokens * self.history_budget)
            history_str = self._truncate_history(kwargs['history'], history_budget_tokens)
            tokens_used += self.count_tokens(history_str)
        
        passage_tokens_budget = available_content_tokens - tokens_used

        if 'passages_context' in kwargs and kwargs['passages_context']:
            passage_str = self._truncate_passages(kwargs['passages_context'], passage_tokens_budget)
        
        if 'history' in kwargs:
            final_components['history_str'] = history_str
        if 'passages_context' in kwargs:
            final_components['passages_context'] = passage_str

        final_prompt = template.format(**final_components)
        
        if self.count_tokens(final_prompt) > max_tokens:
            encoded_prompt = self.tokenizer.encode(final_prompt)
            truncated_encoded = encoded_prompt[:max_tokens]
            final_prompt = self.tokenizer.decode(truncated_encoded, skip_special_tokens=True)
            logging.warning("Prompt exceeded budget after assembly and was hard-truncated.")
            
        return final_prompt