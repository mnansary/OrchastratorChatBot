# --- START OF MODIFIED FILE: cogops/agent.py ---

import os
import yaml
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, List, Tuple

from openai import APIConnectionError, APITimeoutError
from requests.exceptions import RequestException

from cogops.prompt import AGENT_PROMPT
from cogops.tools.tools import tools_list, available_tools_map
from cogops.models.qwen3async_llm import AsyncLLMService
from cogops.tools.private.user_tools import generate_full_user_context_markdown
from cogops.utils.token_manager import TokenManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChatAgent:
    """
    A STATELESS, end-to-end conversational agent.
    REASON FOR CHANGE: This agent is no longer initialized per-session. It is created
    once and holds no session-specific state (like history or user_meta). All dynamic
    context is passed directly into its processing methods. This makes the application
    scalable and robust.
    """
    def __init__(self, config_path: str):
        """
        Initializes the stateless ChatAgent. This is done only ONCE on application startup.
        """
        logging.info("Initializing STATELESS ChatAgent singleton...")
        self.config = self._load_config(config_path)

        # --- Agent Identity (Static) ---
        self.agent_name = self.config.get('agent_name', 'Bengal Meat Assistant')
        self.agent_story = self.config.get('agent_story', 'I am a helpful AI assistant.')

        # --- Core Services (Static) ---
        self.llm_service = self._initialize_llm_service()
        self.token_manager = self._initialize_token_manager()

        # --- Tool Configuration (Static) ---
        self.tools_schema = tools_list
        self.tool_functions = available_tools_map
        self.tools_description = json.dumps(self.tools_schema, indent=4)

        # --- Response Templates (Static) ---
        self.response_templates = self.config['response_templates']
        logging.info("✅ Stateless ChatAgent singleton initialized.")

    def _load_config(self, config_path: str) -> Dict:
        """Loads the agent's YAML configuration file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"[FATAL ERROR] Configuration file not found at: {config_path}")
            raise

    def _initialize_llm_service(self) -> AsyncLLMService:
        """Initializes the asynchronous LLM service client from configuration."""
        cfg = self.config['llm_service']
        api_key = os.getenv(cfg['api_key_env'])
        model = os.getenv(cfg['model_name_env'])
        url = os.getenv(cfg['base_url_env'])
        max_tokens = cfg.get('max_context_tokens', 32000)
        if not all([api_key, model, url]):
            raise ValueError("Missing LLM service environment variables.")
        return AsyncLLMService(api_key, model, url, max_tokens)

    def _initialize_token_manager(self) -> TokenManager:
        """Initializes the TokenManager for safe prompt construction."""
        tm_config = self.config['token_management']
        tokenizer_model = os.getenv(tm_config['tokenizer_model_name_env'])
        if not tokenizer_model:
            raise ValueError("Missing tokenizer model environment variable.")
        return TokenManager(
            model_name=tokenizer_model,
            reservation_tokens=tm_config['prompt_template_reservation_tokens'],
            history_budget=tm_config['history_truncation_budget']
        )

    async def generate_user_context(self, session_meta: Dict[str, Any]) -> str:
        """
        Generates user-specific context (profile, orders) for a logged-in user.
        REASON FOR CHANGE: This is now a utility method that returns the context string
        instead of setting an instance variable.

        Returns:
            str: A Markdown string of the user's context, or a default for guests.
        """
        if not session_meta.get('user_id'):
            return "# User Context\n\n*This is a guest user session.*"
        try:
            # Run the blocking network calls in a separate thread.
            context_string = await asyncio.to_thread(
                generate_full_user_context_markdown,
                session_meta
            )
            return context_string
        except Exception as e:
            logging.error(f"Failed to enrich user context for user {session_meta['user_id']}: {e}", exc_info=True)
            return "# User Context\n\n*Error: Could not retrieve user profile and order data.*"

    async def generate_welcome_message(self, session_meta: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generates a welcome message, now accepting session_meta as an argument.
        """
        if session_meta.get('user_id'):
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে আবার স্বাগতম! আমি আপনার ব্যক্তিগত সহকারী, {self.agent_name}। আপনাকে কীভাবে সাহায্য করতে পারি?"
        else:
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে স্বাগতম! আমি {self.agent_name}। আমি আপনাকে আমাদের পণ্য, অফার এবং স্টোর খুঁজে পেতে সাহায্য করতে পারি। বলুন, কীভাবে শুরু করতে পারি?"
        yield {"type": "welcome_message", "content": welcome_text}

    async def process_query(
        self,
        user_query: str,
        session_meta: Dict[str, Any],
        history: List[Tuple[str, str]],
        location_context: str,
        store_catalog: str,
        user_context: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Processes a user's query using the provided, complete context for this turn.
        REASON FOR CHANGE: This method is now stateless. It receives all required
        context as arguments for a single processing cycle.
        """
        logging.info(f"--- Processing Query: '{user_query}' for store_id: {session_meta.get('store_id')} ---")

        try:
            master_prompt = self.token_manager.build_safe_prompt(
                template=AGENT_PROMPT,
                max_tokens=self.llm_service.max_context_tokens,
                agent_name=self.agent_name,
                agent_story=self.agent_story,
                tools_description=self.tools_description,
                history=history,
                user_query=user_query,
                session_meta=json.dumps(session_meta, indent=2),
                user_context=user_context,
                location_context=location_context,
                store_catalog=store_catalog
            )

            messages = [
                {"role": "system", "content": master_prompt},
                {"role": "user", "content": user_query}
            ]

            llm_call_params = self.config.get('llm_call_parameters', {})

            stream_generator = self.llm_service.stream_with_tool_calls(
                messages=messages,
                tools=self.tools_schema,
                available_tools=self.tool_functions,
                session_meta=session_meta,
                **llm_call_params
            )

            async for event in stream_generator:
                yield event

        except (APIConnectionError, APITimeoutError, RequestException) as e:
            logging.error(f"A network service is unavailable. Underlying error: {e}")
            yield {"type": "error", "content": self.response_templates['error_fallback']}
        except Exception as e:
            logging.error(f"An unexpected error occurred during query processing: {e}", exc_info=True)
            yield {"type": "error", "content": self.response_templates['error_fallback']}


# --- END OF MODIFIED FILE: cogops/agent.py ---