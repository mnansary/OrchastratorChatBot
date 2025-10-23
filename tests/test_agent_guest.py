# FILE: tests/test_agent_guest.py

import asyncio
import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any

# --- Pre-run Setup ---
# Load environment variables from the .env file in the project root.
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Agent Import ---
# This assumes you are running the script from the root of your project directory.
from cogops.agent import ChatAgent

# --- Test Configuration ---
AGENT_CONFIG_PATH = "configs/config.yaml"

# This simulates the session metadata that the frontend would send for a guest user.
# The store_id is essential.
GUEST_SESSION_META: Dict[str, Any] = {
    "store_id": 37,  # Bengal Meat Butcher Shop Mohammadpur
    "user_id": None,
    "access_token": None,
    "refresh_token": None
}


async def main():
    """Main function to orchestrate a simulated guest user conversation."""
    print("🚀 STARTING AGENT GUEST SESSION TEST 🚀")
    print(f"Simulating a guest user for Store ID: {GUEST_SESSION_META['store_id']}")

    # --- Step 1: Initialize the Agent for a New Session ---
    # This mimics what your api_service.py does when it receives session_meta for the first time.
    try:
        agent = ChatAgent(config_path=AGENT_CONFIG_PATH, session_meta=GUEST_SESSION_META)
        print("✅ Agent initialized successfully for the session.")
    except Exception as e:
        logging.error(f"❌ FAILED to initialize ChatAgent. Error: {e}", exc_info=True)
        return

    # --- Step 2: Test the Welcome Message ---
    print("\n" + "="*80)
    print("▶️  TESTING: Welcome Message Generation")
    print("="*80)
    print("🤖 Agent Welcome: ", end="", flush=True)
    async for event in agent.generate_welcome_message():
        if event["type"] == "welcome_message":
            print(event["content"])
    
    # --- Step 3: Simulate a Conversation ---
    test_queries = [
        "আপনি কে?",
        "আপনাদের রিটার্ন পলিসি কি?",
        "What kinds of products do you have?",
        "বিফ কিমা আছে?",
        "দাম কত? আর গরুর মাংসের উপর কোন অফার আছে?",
        "বাংলাদেশের প্রধানমন্ত্রীর নাম কী?",
    ]

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
            logging.error(f"❌ FAILED! An error occurred while processing query #{i}.", exc_info=True)

    print("\n" + "#"*80)
    print("🏁 AGENT GUEST SESSION TEST COMPLETE 🏁")
    print("#"*80)


if __name__ == "__main__":
    # Ensure all necessary environment variables for the agent and its tools are set.
    required_vars = [
        "COMPANY_API_BASE_URL",
        "VLLM_API_KEY",
        "VLLM_MODEL_NAME",
        "VLLM_BASE_URL",
        "CHROMA_DB_HOST",
        "CHROMA_DB_PORT",
        "TRITON_EMBEDDER_URL",
        "POSTGRES_HOST" # Add other DB vars if needed
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n❌ ERROR: The following required environment variables are not set: {', '.join(missing_vars)}")
        print("Please ensure your .env file is correctly configured in the project root.")
    else:
        asyncio.run(main())