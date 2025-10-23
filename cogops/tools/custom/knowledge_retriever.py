# tools.py
# This script defines various tool functions that can be used by the LLM service.
# Currently includes: get_current_time and retrieve_knowledge.
# The VectorRetriever class is assumed to be in cogops.retriver.vector_search.
# Also includes the OpenAI-compatible tools_list and available_tools_map for easy import.

import os
import json
import asyncio
import logging
from datetime import datetime
from collections import defaultdict
import yaml
import chromadb
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
load_dotenv()
# --- Custom Module Imports ---
# Adjust these paths based on your actual project structure
from cogops.retriver.vector_search import VectorRetriever  # Assuming this is where VectorRetriever is defined

CONFIG_CONSTANT=os.getenv("CONFIG_FILE_PATH")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_current_time() -> str:
    """Returns the current server date and time as a formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def retrieve_knowledge(query: str) -> List[Dict[str, Any]]:
    """Async tool function to retrieve passages from the knowledge base using VectorRetriever."""
    retriever = VectorRetriever(config_path=CONFIG_CONSTANT)
    try:
        passages = await retriever.retrieve_passages(query)
        return passages
    except Exception as e:
        logging.error(f"Error in retrieve_knowledge: {e}", exc_info=True)
        return []
    finally:
        retriever.close()

