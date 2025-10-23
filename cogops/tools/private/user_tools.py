# FILE: tools/private/user_tools.py

import os
import requests
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL")
if not BASE_URL:
    raise ValueError("FATAL ERROR: COMPANY_API_BASE_URL environment variable is not set.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- SIMPLIFIED HELPER FUNCTION ---
def _make_private_request(endpoint: str, session_meta: Dict[str, Any], method: str = 'GET', payload: Optional[Dict] = None) -> Optional[Dict]:
    """Handles authenticated requests by sending both access and refresh tokens in the headers."""
    access_token = session_meta.get('access_token')
    refresh_token = session_meta.get('refresh_token')

    if not all([access_token, refresh_token]):
        logging.error(f"Missing access_token or refresh_token for a private API call to {endpoint}.")
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "refreshToken": refresh_token,
        "Content-Type": "application/json"
    }
    api_url = f"{BASE_URL}/{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(api_url, headers=headers, timeout=10)
        elif method == 'POST':
            response = requests.post(api_url, headers=headers, json=payload, timeout=10)
        else: # Should not happen
            logging.error(f"Unsupported HTTP method: {method}")
            return None
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error for {endpoint}: {http_err} - {http_err.response.text}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request failed for {endpoint}: {req_err}")
        return None


def fetch_user_profile(session_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetches the profile details of the logged-in user."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_user_profile: Attempted to call without user_id. Skipping.")
        return None

    endpoint = f"customer/{user_id}"
    logging.info(f"Fetching user profile from: {endpoint}")
    data = _make_private_request(endpoint, session_meta)
    
    if data and data.get('data'):
        user_info = data['data'][0]
        profile_context = {
            "name": user_info.get("customer_name"), "email": user_info.get("email"),
            "phone": user_info.get("phone"), "gender": user_info.get("gender"),
            "dob": user_info.get("dob"), "city": user_info.get("city")
        }
        logging.info(f"Successfully fetched profile for user_id: {user_id}")
        return profile_context
        
    logging.warning(f"Failed to fetch or parse profile for user_id: {user_id}")
    return None


def fetch_user_loyalty_status(session_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetches the loyalty points and wallet balance for the logged-in user."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_user_loyalty_status: Called for a session without a user_id. Skipping.")
        return None

    endpoint = "customer/customerPointAndBalance"
    logging.info(f"Fetching loyalty status for user_id: {user_id}")
    data = _make_private_request(endpoint, session_meta)

    if data and 'data' in data:
        loyalty_data = data['data']
        loyalty_context = {"points": loyalty_data.get("point"), "balance": loyalty_data.get("balance")}
        logging.info(f"Successfully fetched loyalty status for user_id: {user_id}")
        return loyalty_context

    logging.warning(f"Failed to fetch or parse loyalty status for user_id: {user_id}")
    return None