# FILE: cogops/agent.py

import os
import yaml
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, List, Tuple

from dotenv import load_dotenv
load_dotenv()

# --- Exception Imports for Network Errors ---
from openai import APIConnectionError, APITimeoutError
from requests.exceptions import RequestException

# --- Core Component Imports ---
from cogops.prompt import get_agent_prompt
from cogops.tools.tools import tools_list, available_tools_map
from cogops.models.qwen3async_llm import AsyncLLMService
from cogops.utils.token_manager import TokenManager

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChatAgent:
    """
    An end-to-end conversational agent that uses a tool-based pipeline.
    This agent is session-aware and holds user metadata for contextual tool calls.
    """
    def __init__(self, config_path: str, session_meta: Dict[str, Any]):
        """
        Initializes the ChatAgent for a specific user session.

        Args:
            config_path: Path to the main configuration YAML file.
            session_meta: A dictionary containing session-specific data like store_id and user_id.
        """
        logging.info(f"Initializing ChatAgent with session_meta: {session_meta}")
        self.config = self._load_config(config_path)
        
        # --- Session & Agent Identity ---
        self.session_meta = session_meta
        self.agent_name = self.config.get('agent_name', 'Bengal Meat Assistant')
        self.agent_story = self.config.get('agent_story', 'I am a helpful AI assistant from Bengal Meat.')

        # --- Initialize LLM Service ---
        self.llm_service = self._initialize_llm_service()

        # --- CORRECTED: Initialize Tokenizer ---
        # The tokenizer should use the same model as the LLM service for accurate counting,
        # as defined in the config file.
        logging.info(f"Initializing TokenManager with model: {self.llm_service.model}")
        self.token_manager = TokenManager(
            model_name=self.llm_service.model,
            reservation_tokens=0, # Not used in the new prompt structure
            history_budget=1.0   # Not used in the new prompt structure
        )
        # ----------------------------------------

        # --- Conversation and Tool Management ---
        self.history: List[Tuple[str, str]] = []
        self.history_window = self.config['conversation']['history_window']
        self.llm_call_params = self.config.get('llm_call_parameters', {})
        self.response_templates = self.config['response_templates']
        
        self.tools_schema = tools_list
        self.tool_functions = available_tools_map
        self.tools_description = json.dumps(self.tools_schema, indent=4)

        logging.info("✅ ChatAgent initialized successfully for the session.")

    def _load_config(self, config_path: str) -> Dict:
        logging.info(f"Loading configuration from: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"[FATAL ERROR] Configuration file not found at: {config_path}")
            raise
    
    def _initialize_llm_service(self) -> AsyncLLMService:
        logging.info("Initializing primary LLM service...")
        cfg = self.config['llm_service']
        api_key = os.getenv(cfg['api_key_env'])
        model = os.getenv(cfg['model_name_env'])
        url = os.getenv(cfg['base_url_env'])
        max_tokens = cfg.get('max_context_tokens', 32000)
        
        if not all([api_key, model, url]):
            raise ValueError(f"Missing environment variables for LLM service '{cfg['name']}'")
            
        return AsyncLLMService(api_key, model, url, max_tokens)

    def _format_conversation_history(self) -> str:
        if not self.history:
            return "No conversation history yet."
        return "\n---\n".join([f"User: {u}\nAI: {a}" for u, a in self.history])

    async def generate_welcome_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        logging.info("Generating welcome message for the session.")
        user_id = self.session_meta.get('user_id')

        if user_id:
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে স্বাগতম! আমি আপনার ব্যক্তিগত সহকারী, {self.agent_name}। আপনাকে কীভাবে সাহায্য করতে পারি?"
        else:
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে স্বাগতম! আমি {self.agent_name}। আমি আপনাকে আমাদের পণ্য, অফার এবং স্টোর খুঁজে পেতে সাহায্য করতে পারি। বলুন, কীভাবে শুরু করতে পারি?"

        yield {"type": "welcome_message", "content": welcome_text}
        
    async def process_query(self, user_query: str) -> AsyncGenerator[Dict[str, Any], None]:
        logging.info(f"\n--- Processing Query: '{user_query}' for store_id: {self.session_meta.get('store_id')} ---")
        
        try:
            conversation_history_str = self._format_conversation_history()

            master_prompt = get_agent_prompt(
                agent_name=self.agent_name,
                agent_story=self.agent_story,
                tools_description=self.tools_description,
                conversation_history=conversation_history_str,
                user_query=user_query,
                session_meta=self.session_meta
            )
            
            messages = [
                {"role": "system", "content": master_prompt},
                {"role": "user", "content": user_query}
            ]

            full_final_answer = []
            stream_generator = self.llm_service.stream_with_tool_calls(
                messages=messages,
                tools=self.tools_schema,
                available_tools=self.tool_functions,
                **self.llm_call_params
            )

            async for chunk in stream_generator:
                full_final_answer.append(chunk)
                yield {"type": "answer_chunk", "content": chunk}

            final_answer_str = "".join(full_final_answer).strip()

            if final_answer_str:
                self.history.append((user_query, final_answer_str))
            
            if len(self.history) > self.history_window:
                self.history.pop(0)

        except (APIConnectionError, APITimeoutError, RequestException) as e:
            logging.error(f"A network service is unavailable. Underlying error: {e}")
            yield {"type": "error", "content": self.response_templates['error_fallback']}
        except Exception as e:
            logging.error(f"An unexpected error occurred during query processing: {e}", exc_info=True)
            yield {"type": "error", "content": self.response_templates['error_fallback']}