# FILE: tests/test_agent_setwise.py

import asyncio
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any

# --- Pre-run Setup ---
# Load environment variables from the .env file in the project root.
load_dotenv()

# --- Agent Import ---
# This assumes you are running the script from the root of your project directory.
from cogops.agent import ChatAgent

# --- Test Configuration ---
AGENT_CONFIG_PATH = "configs/config.yaml"
# The script expects the questions file and the log output folder to be in the same 'tests' directory.
TESTS_DIR = os.path.dirname(__file__)
QUESTIONS_FILE_PATH = os.path.join(TESTS_DIR, "test_questions_guest.json")
LOG_DIR = TESTS_DIR  # Log will be created in the same 'tests/' folder

# This simulates the session metadata that the frontend would send for a guest user.
GUEST_SESSION_META: Dict[str, Any] = {
    "store_id": 37,  # Default store for testing: Bengal Meat Butcher Shop Mohammadpur
    "user_id": None,
    "access_token": None,
    "refresh_token": None
}

def setup_logging(log_filename: str):
    """Configures logging to write to both the console and a file."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Get the root logger
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


async def main():
    """Main function to orchestrate the set-wise agent testing."""
    # --- 1. Setup Logging ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(LOG_DIR, f"guest_session_test_run_{timestamp}.log")
    setup_logging(log_filename)
    
    logging.info("🚀 STARTING BENGAL MEAT AGENT SET-WISE TEST 🚀")
    logging.info(f"Full conversation log will be saved to: {log_filename}")

    # --- 2. Load Test Questions ---
    try:
        with open(QUESTIONS_FILE_PATH, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        test_sets = test_data.get("test_sets", [])
        logging.info(f"Successfully loaded {len(test_sets)} test sets from '{QUESTIONS_FILE_PATH}'.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"❌ FATAL: Could not load or parse the questions file. Error: {e}")
        return

    # --- 3. Initialize the Agent for a Single Session ---
    try:
        agent = ChatAgent(config_path=AGENT_CONFIG_PATH, session_meta=GUEST_SESSION_META)
        logging.info("✅ Agent initialized successfully for the session.")
    except Exception as e:
        logging.error(f"❌ FATAL: Could not initialize ChatAgent. Error: {e}", exc_info=True)
        return

    # --- 4. Log the Welcome Message ---
    logging.info("\n" + "#"*80 + "\n# 1. GENERATING WELCOME MESSAGE\n" + "#"*80)
    async for event in agent.generate_welcome_message():
        logging.info(f"[WELCOME]: {event.get('content')}")

    # --- 5. Run Tests Set by Set ---
    for test_set in test_sets:
        set_name = test_set.get('set_name', 'Unnamed Set')
        questions = test_set.get('questions', [])
        
        logging.info("\n" + "#"*80 + f"\n# STARTING: {set_name}\n" + "#"*80)
        
        for i, query in enumerate(questions, 1):
            logging.info(f"\n{'='*80}\n[SET: {set_name}] - Query #{i}: {query}\n{'='*80}")
            
            full_response_chunks = []
            try:
                # Process the query and stream the response
                async for event in agent.process_query(query):
                    if event["type"] == "answer_chunk":
                        full_response_chunks.append(event["content"])
                    elif event["type"] == "error":
                        logging.error(f"[AGENT ERROR EVENT]: {event['content']}")
                
                # Log the final assembled response
                final_response = "".join(full_response_chunks)
                logging.info(f"\n--- Final Assembled Response ---\n{final_response}\n--------------------------------")

            except Exception as e:
                logging.error(f"❌ CRITICAL FAILURE during query processing for '{query}'.", exc_info=True)

    logging.info("\n" + "#"*80 + "\n🏁 AGENT SET-WISE TEST COMPLETE 🏁\n" + "#"*80)


if __name__ == "__main__":
    # Ensure all necessary environment variables are set.
    required_vars = [
        "COMPANY_API_BASE_URL", "VLLM_API_KEY", "VLLM_MODEL_NAME", "VLLM_BASE_URL",
        "CHROMA_DB_HOST", "CHROMA_DB_PORT", "TRITON_EMBEDDER_URL", "POSTGRES_HOST"
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n❌ ERROR: The following required environment variables are not set: {', '.join(missing_vars)}")
        print("Please ensure your .env file is correctly configured in the project root.")
    else:
        asyncio.run(main())