# FILE: tests/test_agent_sessions.py

import asyncio
import os
import json
import logging
import argparse
from dotenv import load_dotenv
from typing import Dict, Any, List

# --- Pre-run Setup ---
# Load environment variables from the .env file in the project root.
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Agent Import ---
from cogops.agent import ChatAgent

# --- Test Configuration ---
AGENT_CONFIG_PATH = "configs/config.yaml"


async def run_agent_test_session(session_meta: Dict[str, Any], test_queries: List[str], session_type: str):
    """
    Orchestrates a full test session for a given session_meta (guest or registered).
    """
    header = f"🚀 STARTING AGENT SESSION TEST: {session_type.upper()} USER 🚀"
    print("\n" + "#"*80)
    print(header)
    print(f"Using Session Meta: {session_meta}")
    print("#"*80)

    # --- Step 1: Initialize the Agent for the Session ---
    try:
        agent = ChatAgent(config_path=AGENT_CONFIG_PATH, session_meta=session_meta)
        print("✅ Agent initialized successfully for the session.")
    except Exception as e:
        logging.error(f"❌ FAILED to initialize ChatAgent for {session_type} user. Error: {e}", exc_info=True)
        return

    # --- Step 2: Enrich Context and Generate Welcome Message ---
    # This is the critical step that populates context for registered users.
    await agent._enrich_context()
    
    print("\n" + "="*80)
    print("▶️  TESTING: Welcome Message Generation")
    print("="*80)
    print("🤖 Agent Welcome: ", end="", flush=True)
    async for event in agent.generate_welcome_message():
        if event["type"] == "welcome_message":
            print(event["content"])
    
    # --- Step 3: Simulate the Conversation ---
    for i, query in enumerate(test_queries, 1):
        print("\n" + "="*80)
        print(f"▶️  TESTING: Query #{i}")
        print("="*80)
        print(f"🗣️  User Query: {query}")
        print("🤖 Agent Response: ", end="", flush=True)

        try:
            async for event in agent.process_query(query):
                if event["type"] == "answer_chunk":
                    print(event["content"], end="", flush=True)
                elif event["type"] == "error":
                    print(f"\n[AGENT ERROR] {event['content']}")
            print()  # for a newline after the streamed response
        except Exception as e:
            logging.error(f"❌ FAILED! An error occurred while processing query #{i} for {session_type} user.", exc_info=True)

    print(f"\n🏁 {session_type.upper()} USER SESSION TEST COMPLETE 🏁")


async def main(session_meta_path: str):
    """Main function to load session data and run tests for both guest and registered users."""

    # --- Define a concise set of queries for functional testing ---
    functional_test_queries = [
        "Hi there!",
        "What kinds of beef products do you have?",
        "What was in my last order?", # This query will behave differently for each user type
        "That's great, thanks!"
    ]

    # --- Test 1: Guest Session ---
    guest_session_meta: Dict[str, Any] = {
        "store_id": 37,
        "user_id": None,
        "access_token": None,
        "refresh_token": None
    }
    await run_agent_test_session(guest_session_meta, functional_test_queries, "Guest")

    # --- Test 2: Registered User Session ---
    try:
        with open(session_meta_path, 'r') as f:
            registered_user_meta = json.load(f)
        # Ensure correct data types
        registered_user_meta['user_id'] = int(registered_user_meta['user_id'])
        registered_user_meta['store_id'] = int(registered_user_meta['store_id'])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"\n❌ FATAL ERROR: Could not load or parse the session_meta JSON file. Aborting registered user test. Error: {e}")
        return
        
    await run_agent_test_session(registered_user_meta, functional_test_queries, "Registered User")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run functional tests for the ChatAgent with both guest and registered user sessions.")
    parser.add_argument(
        '--session_meta',
        type=str,
        required=True,
        help='Path to the JSON file containing registered user session metadata (access_token, refresh_token, user_id, store_id).'
    )
    args = parser.parse_args()

    # Ensure all necessary environment variables for the agent and its tools are set.
    required_vars = [
        "COMPANY_API_BASE_URL", "VLLM_API_KEY", "VLLM_MODEL_NAME", "VLLM_BASE_URL",
        "CHROMA_DB_HOST", "CHROMA_DB_PORT", "TRITON_EMBEDDER_URL", "POSTGRES_HOST"
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n❌ ERROR: The following required environment variables are not set: {', '.join(missing_vars)}")
        print("Please ensure your .env file is correctly configured in the project root.")
    else:
        asyncio.run(main(args.session_meta))