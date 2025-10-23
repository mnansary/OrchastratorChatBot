# FILE: tools/public/promotions_and_details.py

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


# --- REFINED FUNCTION ---
def get_all_products_for_store(store_id: int, session_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    An efficient function to fetch a comprehensive list of all products available at a specific store.
    It uses the customer_id from session_meta if available to fetch personalized prices.
    Use this for broad queries like 'What do you have in stock?' or 'List all your products'.

    Args:
        store_id: The ID of the store for which to fetch the product list.
        session_meta: The user's session data, which may contain a 'user_id'.
    """
    api_url = f"{BASE_URL}/product/productListForChatbot"
    
    # Dynamically select customer_id
    customer_id_to_use = session_meta.get('user_id') or GUEST_CUSTOMER_ID
    
    logging.info(f"Requesting full product list for store_id '{store_id}' and customer_id '{customer_id_to_use}'.")

    payload = {
        "store_id": str(store_id),
        "company_id": 1,
        "order_by": "popularity",
        "customer_id": customer_id_to_use
    }

    try:
        response = requests.post(api_url, json=payload, timeout=20)
        response.raise_for_status()
        
        product_list = response.json().get('data', {}).get(str(store_id), [])

        simplified_list = [
            {
                "product_id": product.get("product_id"),
                "name": product.get("name"),
                "category": product.get("category_name"),
                "price_bdt": product.get("mrp"),
                "is_in_stock": "Yes" if product.get("stockQuantity", 0) > 0 else "No",
                "has_discount": "Yes" if product.get("discount_value", 0) > 0 else "No"
            }
            for product in product_list
        ]

        logging.info(f"Successfully retrieved {len(simplified_list)} products for store_id '{store_id}'.")
        return simplified_list

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch chatbot product list for store_id '{store_id}'. Error: {e}")
        return []


# --- REFINED FUNCTION ---
def get_product_details(product_id: int, store_id: int, session_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Retrieves exhaustive details for a single product.
    It uses the customer_id from session_meta if available to fetch personalized prices.
    Use this as a follow-up when a user asks for more information about a specific product.

    Args:
        product_id: The unique ID of the product.
        store_id: The ID of the store to check for availability and details.
        session_meta: The user's session data, which may contain a 'user_id'.
    """
    api_url = f"{BASE_URL}/product/getListOfProductDetails"
    
    # Dynamically select customer_id
    customer_id_to_use = session_meta.get('user_id') or GUEST_CUSTOMER_ID
    
    logging.info(f"Requesting details for product_id '{product_id}' at store_id '{store_id}' for customer_id '{customer_id_to_use}'.")

    payload = {
        "product_id": product_id,
        "store_id": store_id,
        "customer_id": customer_id_to_use
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()

        product_data = response.json().get('data', {}).get('productData', [])

        if not product_data:
            logging.warning(f"No details found for product_id '{product_id}' at store_id '{store_id}'.")
            return None

        details = product_data[0]
        
        simplified_details = {
            "name": details.get("name"),
            "description": details.get("details"),
            "price_bdt": details.get("mrp"),
            "weight_gm": details.get("weight_in_gm"),
            "stock_quantity": details.get("stockQuantity"),
            "is_in_stock": "Yes" if details.get("stockQuantity", 0) > 0 else "No",
            "category": details.get("product_category_name")
        }

        logging.info(f"Successfully retrieved details for product_id '{product_id}'.")
        return simplified_details

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch details for product_id '{product_id}'. Error: {e}")
        return None