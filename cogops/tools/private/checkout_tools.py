# FILE: tools/private/checkout_tools.py

import os
import requests
import logging
from typing import List, Dict, Any, Optional
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
        else:
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


def fetch_user_saved_addresses(session_meta: Dict[str, Any]) -> Optional[List[Dict[str, str]]]:
    """Fetches the logged-in user's saved shipping/billing addresses."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_user_saved_addresses: Attempted to call without user_id. Skipping.")
        return None

    endpoint = "customer/address/list"
    payload = {"where": {"customer_id": user_id}}
    logging.info(f"Fetching saved addresses for user_id: {user_id}")
    data = _make_private_request(endpoint, session_meta, method='POST', payload=payload)

    if data and data.get('data', {}).get('data'):
        addresses = data['data']['data']
        simplified_addresses = [
            {
                "name": addr.get("name"),
                "address_details": f"House {addr.get('house_no', '')}, Road {addr.get('road_no', '')}, {addr.get('area', '')}, {addr.get('city', '')}",
                "phone": addr.get("phone")
            }
            for addr in addresses
        ]
        logging.info(f"Successfully fetched {len(simplified_addresses)} addresses for user_id: {user_id}")
        return simplified_addresses

    logging.warning(f"Failed to fetch or parse addresses for user_id: {user_id}")
    return None


def fetch_delivery_slots(date: str, session_meta: Dict[str, Any]) -> Optional[List[str]]:
    """Finds available delivery time slots for a specific date."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_delivery_slots: Attempted to call without user_id. Skipping.")
        return None

    endpoint = f"delivery/getDeliveryTimeSlot/{date}"
    logging.info(f"Fetching delivery slots for date: {date}")
    data = _make_private_request(endpoint, session_meta)

    if data and 'data' in data:
        slots = data.get('data') 
        if isinstance(slots, list):
            logging.info(f"Successfully fetched {len(slots)} delivery slots for {date}.")
            return slots

    logging.warning(f"Failed to fetch or parse delivery slots for date: {date}")
    return None


def fetch_payment_options(session_meta: Dict[str, Any]) -> Optional[List[str]]:
    """Fetches the list of enabled payment methods."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_payment_options: Attempted to call without user_id. Skipping.")
        return None
        
    endpoint = "payment-method/list"
    payload = {"where": {"is_enabled": 1}}
    logging.info("Fetching available payment methods.")
    data = _make_private_request(endpoint, session_meta, method='POST', payload=payload)
    
    if data and data.get('data', {}).get('data'):
        methods_data = data['data']['data']
        method_names = [method.get('name') for method in methods_data if method.get('name')]
        logging.info(f"Successfully fetched {len(method_names)} payment methods.")
        return method_names
        
    logging.warning(f"Failed to fetch or parse payment methods.")
    return None