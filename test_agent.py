# FILE: test_agent.py

import asyncio
import os
import json
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any, List

# --- Pre-run Setup ---
# Load environment variables from the .env file in the project root.
load_dotenv()

# --- Agent & Context Imports ---
# This assumes you are running the script from the root of your project directory.
from cogops.agent import ChatAgent
# Import the context_manager to build static context, just like the real API service.
from cogops.context_manager import context_manager

# --- Test Configuration ---
AGENT_CONFIG_PATH = "configs/config.yaml"
# The log output folder is the same 'tests' directory where this script resides.
LOG_DIR = os.path.dirname(__file__) 

def setup_logging(log_filename: str):
    """Configures logging to write to both the console and a file."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicate logs if re-run in the same process
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # File Handler
    file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)


async def run_test_for_session(session_meta: Dict[str, Any], test_sets: List[Dict], session_type: str):
    """
    Initializes an agent for a specific session type (Guest or Registered),
    enriches its context, and runs it through a series of test questions.
    """
    header = f"🚀 STARTING TEST RUN FOR: {session_type.upper()} USER 🚀"
    logging.info("\n" + "#"*80 + f"\n{header}\n" + "#"*80)
    logging.info(f"Using Session Meta: {json.dumps(session_meta, indent=2)}")

    # --- 1. Initialize the Agent for this specific session ---
    try:
        # The agent MUST be initialized with the pre-built static context.
        agent = ChatAgent(
            config_path=AGENT_CONFIG_PATH,
            session_meta=session_meta,
            location_context=context_manager.location_context,
            store_catalog=context_manager.store_catalog
        )
        logging.info(f"✅ Agent initialized successfully for {session_type} session.")
    except Exception as e:
        logging.error(f"❌ FATAL: Could not initialize ChatAgent for {session_type} session. Error: {e}", exc_info=True)
        return

    # --- 2. Enrich context (for registered users) and get welcome message ---
    logging.info("Enriching session-specific context (profile, orders)...")
    await agent._enrich_context() # This loads user data if the session_meta has a user_id.
    logging.info("Context enrichment step complete.")

    logging.info("\n" + "="*80 + "\n# 1. GENERATING WELCOME MESSAGE\n" + "="*80)
    async for event in agent.generate_welcome_message():
        logging.info(f"[WELCOME]: {event.get('content')}")

    # --- 3. Run through all test sets and questions ---
    for test_set in test_sets:
        set_name = test_set.get('set_name', 'Unnamed Set')
        questions = test_set.get('questions', [])
        
        logging.info("\n" + "#"*80 + f"\n# STARTING TEST SET: {set_name}\n" + "#"*80)
        
        for i, query in enumerate(questions, 1):
            logging.info(f"\n{'='*80}\n[SET: {set_name}] - Query #{i}: {query}\n{'='*80}")
            
            full_response_chunks = []
            try:
                # Process the query and log all events as they stream in
                async for event in agent.process_query(query):
                    event_type = event.get("type", "unknown")
                    
                    if event_type == "answer_chunk":
                        full_response_chunks.append(event["content"])
                    elif event_type == "tool_call":
                        logging.info(f"-> [AGENT ACTION]: Calling tool '{event.get('tool_name', 'N/A')}'...")
                    elif event_type == "error":
                        logging.error(f"[AGENT ERROR EVENT]: {event.get('content')}")
                
                # Log the final assembled response
                final_response = "".join(full_response_chunks).strip()
                if final_response:
                    logging.info(f"\n--- Final Assembled Response ---\n{final_response}\n--------------------------------")
                else:
                    logging.warning("-> Agent produced no final text response for this query.")

            except Exception as e:
                logging.error(f"❌ CRITICAL FAILURE during query processing for '{query}'. Error: {e}", exc_info=True)

    logging.info("\n" + "#"*80 + f"\n🏁 {session_type.upper()} USER TEST RUN COMPLETE 🏁\n" + "#"*80)


async def main(questions_path: str, session_meta_path: str):
    """
    Main function to orchestrate the entire agent evaluation pipeline for
    both guest and registered user sessions.
    """
    # --- 1. Setup Logging ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(LOG_DIR, f"agent_evaluation_run_{timestamp}.log")
    setup_logging(log_filename)
    
    logging.info("🚀 STARTING BENGAL MEAT AGENT EVALUATION SCRIPT 🚀")
    logging.info(f"Full conversation log will be saved to: {log_filename}")

    # --- 2. Load Evaluation Questions ---
    try:
        with open(questions_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        test_sets = test_data.get("test_sets", [])
        if not test_sets:
            raise ValueError("No 'test_sets' found in the questions file.")
        logging.info(f"✅ Successfully loaded {len(test_sets)} test sets from '{questions_path}'.")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logging.error(f"❌ FATAL: Could not load or parse the questions file '{questions_path}'. Error: {e}")
        return

    # --- 3. Build Static Context (once for the entire script run) ---
    logging.info("Building static context (locations, catalog) for all sessions...")
    # Define defaults for the initial context build. This context is then shared
    # by all agent instances created during this test run.
    GUEST_CUSTOMER_ID = "369"
    DEFAULT_STORE_ID = 37 
    context_manager.build_static_context(store_id=DEFAULT_STORE_ID, customer_id=GUEST_CUSTOMER_ID)
    logging.info("✅ Static context build complete.")

    # --- 4. Run Guest User Test Session ---
    guest_session_meta: Dict[str, Any] = {
        "store_id": 37,
        "user_id": None,
        "access_token": None,
        "refresh_token": None
    }
    await run_test_for_session(guest_session_meta, test_sets, "Guest")

    # --- 5. Run Registered User Test Session ---
    try:
        with open(session_meta_path, 'r', encoding='utf-8') as f:
            registered_user_meta = json.load(f)
        # Ensure correct data types, as they might be read as strings from JSON
        if 'user_id' in registered_user_meta:
             registered_user_meta['user_id'] = int(registered_user_meta['user_id'])
        if 'store_id' in registered_user_meta:
            registered_user_meta['store_id'] = int(registered_user_meta['store_id'])
        logging.info(f"✅ Successfully loaded registered user session meta from '{session_meta_path}'.")
        await run_test_for_session(registered_user_meta, test_sets, "Registered User")
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
        logging.error(f"❌ SKIPPING registered user test. Could not load/parse '{session_meta_path}'. Error: {e}")

    logging.info("\n" + "#"*80 + "\n🏁 AGENT EVALUATION SCRIPT FINISHED 🏁\n" + "#"*80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run set-wise evaluation tests for the ChatAgent for both guest and registered user sessions.")
    parser.add_argument(
        '--questions',
        type=str,
        required=True,
        help='Path to the JSON file containing the evaluation questions and test sets.'
    )
    parser.add_argument(
        '--session_meta',
        type=str,
        required=True,
        help='Path to the JSON file containing registered user session metadata (e.g., access_token, user_id, store_id).'
    )
    args = parser.parse_args()

    # Ensure all necessary environment variables for the agent and its tools are set.
    required_vars = [
        "COMPANY_API_BASE_URL", "VLLM_API_KEY", "VLLM_MODEL_NAME", "VLLM_BASE_URL",
        "CHROMA_DB_HOST", "CHROMA_DB_PORT", "TRITON_EMBEDDER_URL", "POSTGRES_HOST",
        "CONFIG_FILE_PATH"
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logging.error(f"\n❌ ERROR: The following required environment variables are not set: {', '.join(missing_vars)}")
        logging.error("Please ensure your .env file is correctly configured in the project root.")
    else:
        asyncio.run(main(args.questions, args.session_meta))