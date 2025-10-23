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

        # --- User Context Storage ---
        # This dictionary will be populated with data from private tools for logged-in users.
        self.user_context: Dict[str, Any] = {}

        # --- Initialize LLM Service ---
        self.llm_service = self._initialize_llm_service()

        # --- Initialize Tokenizer ---
        # The tokenizer uses the same model as the LLM service for accurate counting.
        logging.info(f"Initializing TokenManager with model: {self.llm_service.model}")
        self.token_manager = TokenManager(
            model_name=self.llm_service.model,
            reservation_tokens=0,
            history_budget=1.0
        )

        # --- Conversation and Tool Management ---
        self.history: List[Tuple[str, str]] = []
        self.history_window = self.config['conversation']['history_window']
        self.llm_call_params = self.config.get('llm_call_parameters', {})
        self.response_templates = self.config['response_templates']
        
        self.tools_schema = tools_list
        self.tool_functions = available_tools_map
        self.tools_description = json.dumps(self.tools_schema, indent=4)

        logging.info("✅ ChatAgent object created. Context enrichment pending.")

    async def _enrich_context(self):
        """
        Autonomously calls private tools at the start of a session for a logged-in user
        to gather context (profile, order history, etc.). This method is called by the API service
        immediately after the agent is instantiated.
        """
        if not self.session_meta.get('user_id'):
            logging.info("Guest user session. Skipping context enrichment.")
            return

        logging.info(f"Registered user detected (ID: {self.session_meta['user_id']}). Starting context enrichment...")
        
        # --- CORRECTED SECTION ---
        # Instead of calling the functions directly, we wrap them in asyncio.to_thread()
        # to create awaitable tasks that run the blocking code in a separate thread.
        tasks = [
            asyncio.to_thread(self.tool_functions["fetch_user_profile"], self.session_meta),
            asyncio.to_thread(self.tool_functions["fetch_user_order_history"], self.session_meta),
            asyncio.to_thread(self.tool_functions["fetch_user_loyalty_status"], self.session_meta)
        ]
        # --- END OF CORRECTION ---

        # Run all tasks in parallel and get results, allowing for individual failures
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Unpack results safely, checking for exceptions before assigning to context
        profile, history, loyalty = results

        if not isinstance(profile, Exception) and profile:
            self.user_context["profile"] = profile
        if not isinstance(history, Exception) and history:
            self.user_context["order_history"] = history
        if not isinstance(loyalty, Exception) and loyalty:
            self.user_context["loyalty"] = loyalty
        
        logging.info(f"Context enrichment complete. Context gathered: {list(self.user_context.keys())}")

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
        """
        Generates a welcome message that is personalized if user context (e.g., name) was successfully fetched.
        """
        logging.info("Generating welcome message for the session.")
        user_name = self.user_context.get("profile", {}).get("name")

        if user_name:
            # Personalized welcome for registered users
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে স্বাগতম, {user_name}! আমি আপনার ব্যক্তিগত সহকারী, {self.agent_name}। আপনাকে কীভাবে সাহায্য করতে পারি?"
        else:
            # Templated welcome for guest users (or if profile fetch failed)
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে স্বাগতম! আমি {self.agent_name}। আমি আপনাকে আমাদের পণ্য, অফার এবং স্টোর খুঁজে পেতে সাহায্য করতে পারি। বলুন, কীভাবে শুরু করতে পারি?"

        yield {"type": "welcome_message", "content": welcome_text}
        
    async def process_query(self, user_query: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Processes a user's query by constructing a detailed prompt with all available context
        and orchestrating LLM and tool calls.
        """
        logging.info(f"\n--- Processing Query: '{user_query}' for store_id: {self.session_meta.get('store_id')} ---")
        
        try:
            conversation_history_str = self._format_conversation_history()

            master_prompt = get_agent_prompt(
                agent_name=self.agent_name,
                agent_story=self.agent_story,
                tools_description=self.tools_description,
                conversation_history=conversation_history_str,
                user_query=user_query,
                session_meta=self.session_meta,
                user_context=self.user_context  # Pass the enriched context to the prompt
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