# FILE: tools/public/promotions_tools.py

import os
import requests
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from your .env file
load_dotenv()

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL")
if not BASE_URL:
    raise ValueError("FATAL ERROR: COMPANY_API_BASE_URL environment variable is not set.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# This is the default/fallback ID for guest users.
GUEST_CUSTOMER_ID = 369


# --- REFINED FUNCTION ---
def get_active_promotions(store_id: int, session_meta: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Gets a list of all currently active promotions for a specific store.
    It uses the customer_id from session_meta if available for potentially personalized promotions.
    Use this when a user asks about offers, discounts, or current deals.

    Args:
        store_id: The ID of the store to check for promotions.
        session_meta: The user's session data, which may contain a 'user_id'.
    """
    # Dynamically select customer_id: use real ID if logged in, otherwise fallback to guest ID.
    customer_id_to_use = session_meta.get('user_id') or GUEST_CUSTOMER_ID

    api_url = f"{BASE_URL}/data-driven-promotion/activePromotionList/Web/{store_id}/{customer_id_to_use}"
    logging.info(f"Requesting active promotions for store_id '{store_id}' and customer_id '{customer_id_to_use}' from: {api_url}")

    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()

        promotions_data = response.json().get('validPromotionData', [])

        simplified_promotions = [
            {
                "promotion_name": promo.get("name"),
                "description": promo.get("description"),
                "validity_start_date": promo.get("start_date"),
                "validity_end_date": promo.get("end_date")
            }
            for promo in promotions_data
        ]

        logging.info(f"Successfully retrieved {len(simplified_promotions)} active promotions.")
        return simplified_promotions

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch active promotions. Error: {e}")
        return []


