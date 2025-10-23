# FILE: tools/private/user_tools.py

import os
import requests
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# --- CRITICAL: Import the function you want to reuse ---
from cogops.tools.private.order_tools import get_user_order_profile_as_markdown
from cogops.utils.private_api import make_private_request as _make_private_request
load_dotenv()

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL")
if not BASE_URL:
    raise ValueError("FATAL ERROR: COMPANY_API_BASE_URL environment variable is not set.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Original User Profile Function (from your file) ---
def fetch_user_profile(session_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetches the profile details of the logged-in user."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_user_profile: Attempted to call without user_id. Skipping.")
        return None

    endpoint = f"customer/{user_id}"
    logging.info(f"Fetching user profile for user_id: {user_id}")
    data = _make_private_request(endpoint, session_meta, method='GET') # Explicitly GET
    
    if data and data.get('data'):
        user_info = data['data'][0]
        return {
            "name": user_info.get("customer_name"), 
            "email": user_info.get("email"),
            "phone": user_info.get("phone"), 
            "gender": user_info.get("gender"),
        }
        
    logging.warning(f"Failed to fetch or parse profile for user_id: {user_id}")
    return None


# --- NEW MASTER ORCHESTRATOR FUNCTION ---

def generate_full_user_context_markdown(session_meta: Dict[str, Any]) -> str:
    """
    Orchestrates calls to fetch user profile and order history, then combines
    them into a single, comprehensive Markdown string for LLM context.
    """
    if not session_meta.get('user_id'):
        return "# User Context\n\nError: No active user session provided. The user is not logged in."

    logging.info(f"Generating full user context for user_id: {session_meta['user_id']}")
    
    markdown_lines = ["# User Context Summary"]

    # --- 1. Get and format the User Profile section ---
    markdown_lines.append("\n## User Details")
    profile_data = fetch_user_profile(session_meta)
    if profile_data:
        markdown_lines.append(f"- **Name:** {profile_data.get('name', 'N/A')}")
        markdown_lines.append(f"- **Email:** {profile_data.get('email', 'N/A')}")
        markdown_lines.append(f"- **Phone:** {profile_data.get('phone', 'N/A')}")
    else:
        markdown_lines.append("- *User details could not be retrieved.*")

    # --- 2. Reuse the order tool to get the complete, pre-formatted order history section ---
    markdown_lines.append("\n## Recent Order Activity")
    # This call directly returns a formatted Markdown string
    order_history_markdown = get_user_order_profile_as_markdown(session_meta)
    
    # Clean up the redundant header from the reused function for a cleaner final output
    # This makes the final document more seamless.
    if "# User Order Profile" in order_history_markdown:
        order_history_markdown = order_history_markdown.replace("# User Order Profile", "").strip()

    markdown_lines.append(order_history_markdown)

    return "\n".join(markdown_lines)


