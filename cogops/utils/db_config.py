import os
import sys
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from a .env file
load_dotenv()

import os
import sys
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from a .env file in the current directory or parent directories
load_dotenv()

def get_postgres_config():
    """
    Loads PostgreSQL configuration from environment variables.
    Exits the application if any required variable is missing.
    """
    # This mapping ensures the correct keys are created for the SQLAlchemy engine.
    key_map = {
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "port",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_DB": "database",  # <-- This is the corrected key
    }

    config = {key: os.getenv(env_var) for env_var, key in key_map.items()}

    # Validate that all required variables were found in the .env file
    missing = [env_var for env_var, key in key_map.items() if not config[key]]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        sys.exit("Exiting: Database configuration is incomplete.")
        
    logger.info("PostgreSQL configuration loaded successfully.")
    return config

