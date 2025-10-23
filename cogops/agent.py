# FILE: cogops/agent.py

import os
import yaml
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, List, Tuple

# --- Exception Imports for Network Errors ---
from openai import APIConnectionError, APITimeoutError
from requests.exceptions import RequestException

# --- Core Component Imports ---
# We now import the AGENT_PROMPT template directly, as the TokenManager will handle formatting.
from cogops.prompt import AGENT_PROMPT
from cogops.tools.tools import tools_list, available_tools_map
from cogops.models.qwen3async_llm import AsyncLLMService
from cogops.tools.private.user_tools import generate_full_user_context_markdown
# NEW: Import the TokenManager, which is now essential for safe prompt construction.
from cogops.utils.token_manager import TokenManager

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChatAgent:
    """
    An end-to-end conversational agent that uses a tool-based pipeline.
    This agent is session-aware and holds user metadata and context strings.
    """
    def __init__(self, config_path: str, session_meta: Dict[str, Any], location_context: str, store_catalog: str):
        """
        Initializes the ChatAgent for a specific user session.

        Args:
            config_path: Path to the main configuration YAML file.
            session_meta: A dictionary containing session-specific data like store_id and user_id.
            location_context: A pre-generated Markdown string with all location/delivery info.
            store_catalog: A pre-generated Markdown string with the store's product catalog.
        """
        logging.info(f"Initializing ChatAgent with session_meta: {session_meta}")
        self.config = self._load_config(config_path)
        
        # --- Session & Agent Identity ---
        self.session_meta = session_meta
        self.agent_name = self.config.get('agent_name', 'Bengal Meat Assistant')
        self.agent_story = self.config.get('agent_story', 'I am a helpful AI assistant from Bengal Meat.')

        # --- Context Storage ---
        # User-specific context (profile, orders) - loaded by _enrich_context for logged-in users.
        self.user_context: str = "# User Context\n\n*This is a guest user session.*"
        # Static, global context passed in from the ContextManager.
        self.location_context: str = location_context
        self.store_catalog: str = store_catalog

        # --- Initialize LLM and Tokenizer ---
        self.llm_service = self._initialize_llm_service()
        
        # CORRECTED: Initialize and use the TokenManager for safe prompt building.
        tm_config = self.config['token_management']
        tokenizer_model = os.getenv(tm_config['tokenizer_model_name_env'])
        if not tokenizer_model:
            raise ValueError(f"Missing environment variable for tokenizer: {tm_config['tokenizer_model_name_env']}")
        
        self.token_manager = TokenManager(
            model_name=tokenizer_model,
            reservation_tokens=tm_config['prompt_template_reservation_tokens'],
            history_budget=tm_config['history_truncation_budget']
        )

        # --- Conversation and Tool Management ---
        self.history: List[Tuple[str, str]] = []
        self.history_window = self.config['conversation']['history_window']
        self.llm_call_params = self.config.get('llm_call_parameters', {})
        self.response_templates = self.config['response_templates']
        
        self.tools_schema = tools_list
        self.tool_functions = available_tools_map
        self.tools_description = json.dumps(self.tools_schema, indent=4)

        logging.info("✅ ChatAgent object created. User-specific context enrichment pending.")

    async def _enrich_context(self):
        """
        For logged-in users, calls the master context generation function to build
        a single Markdown string containing their profile and order history.
        """
        if not self.session_meta.get('user_id'):
            logging.info("Guest user session. Skipping user-specific context enrichment.")
            return

        logging.info(f"Registered user detected (ID: {self.session_meta['user_id']}). Enriching user context...")
        
        try:
            # Run the blocking network calls in a separate thread to not block the event loop
            context_string = await asyncio.to_thread(
                generate_full_user_context_markdown, 
                self.session_meta
            )
            self.user_context = context_string
            logging.info("User context enrichment complete.")
        except Exception as e:
            logging.error(f"Failed to enrich user context for user {self.session_meta['user_id']}: {e}", exc_info=True)
            self.user_context = "# User Context\n\n*Error: Could not retrieve user profile and order data.*"

    def _load_config(self, config_path: str) -> Dict:
        """Loads the agent's YAML configuration file."""
        logging.info(f"Loading configuration from: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"[FATAL ERROR] Configuration file not found at: {config_path}")
            raise
    
    def _initialize_llm_service(self) -> AsyncLLMService:
        """Initializes the asynchronous LLM service client from configuration."""
        logging.info("Initializing primary LLM service...")
        cfg = self.config['llm_service']
        api_key = os.getenv(cfg['api_key_env'])
        model = os.getenv(cfg['model_name_env'])
        url = os.getenv(cfg['base_url_env'])
        max_tokens = cfg.get('max_context_tokens', 32000)
        
        if not all([api_key, model, url]):
            raise ValueError(f"Missing one or more environment variables for LLM service: Check {cfg['api_key_env']}, {cfg['model_name_env']}, and {cfg['base_url_env']}")
            
        return AsyncLLMService(api_key, model, url, max_tokens)

    def _format_conversation_history(self) -> str:
        """Formats the stored conversation history into a string for the prompt."""
        if not self.history:
            return "No conversation history yet."
        return "\n---\n".join([f"User: {u}\nAssistant: {a}" for u, a in self.history])

    async def generate_welcome_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generates a welcome message that acknowledges if the user is logged in.
        """
        logging.info("Generating welcome message for the session.")
        
        if self.session_meta.get('user_id'):
            # Acknowledges a returning/logged-in user
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে আবার স্বাগতম! আমি আপনার ব্যক্তিগত সহকারী, {self.agent_name}। আপনাকে কীভাবে সাহায্য করতে পারি?"
        else:
            # Standard welcome for guest users
            welcome_text = f"বেঙ্গল মিট-এ আপনাকে স্বাগতম! আমি {self.agent_name}। আমি আপনাকে আমাদের পণ্য, অফার এবং স্টোর খুঁজে পেতে সাহায্য করতে পারি। বলুন, কীভাবে শুরু করতে পারি?"

        yield {"type": "welcome_message", "content": welcome_text}
        
    async def process_query(self, user_query: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Processes a user's query by constructing a detailed, token-safe prompt
        and orchestrating LLM and tool calls.
        """
        logging.info(f"\n--- Processing Query: '{user_query}' for store_id: {self.session_meta.get('store_id')} ---")
        
        try:
            # CRITICAL FIX: Use the TokenManager to build a context-aware and safe prompt.
            # This prevents context overflow errors by truncating history/context if needed.
            master_prompt = self.token_manager.build_safe_prompt(
                template=AGENT_PROMPT,
                max_tokens=self.llm_service.max_context_tokens,
                # Pass all components to the builder. The manager handles formatting.
                agent_name=self.agent_name,
                agent_story=self.agent_story,
                tools_description=self.tools_description,
                history=self.history, # Pass the raw list of tuples
                user_query=user_query,
                session_meta=json.dumps(self.session_meta, indent=2),
                user_context=self.user_context,
                location_context=self.location_context,
                store_catalog=self.store_catalog
            )
            
            messages = [
                {"role": "system", "content": master_prompt},
                {"role": "user", "content": user_query}
            ]

            full_final_answer = []
            # The stream_with_tool_calls function now handles yielding structured events.
            stream_generator = self.llm_service.stream_with_tool_calls(
                messages=messages,
                tools=self.tools_schema,
                available_tools=self.tool_functions,
                session_meta=self.session_meta, # Pass session_meta for private tool calls
                **self.llm_call_params
            )

            async for event in stream_generator:
                # Collect content from 'answer_chunk' events to build the full response for history.
                if event.get("type") == "answer_chunk":
                    full_final_answer.append(event.get("content", ""))
                # Stream the entire event (tool_call or chunk) directly to the frontend.
                yield event

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