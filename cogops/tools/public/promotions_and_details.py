# FILE: tools/public/promotions_and_details.py

import os
import requests
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from your .env file
load_dotenv()

# --- Configuration ---
# This script requires the COMPANY_API_BASE_URL environment variable.
BASE_URL = os.getenv("COMPANY_API_BASE_URL")
if not BASE_URL:
    raise ValueError("FATAL ERROR: COMPANY_API_BASE_URL environment variable is not set.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# A placeholder for guest user ID as seen in the API examples.
# The API may not require it, but we pass it for consistency with the provided collection.
GUEST_CUSTOMER_ID = 369

def get_active_promotions(store_id: int) -> List[Dict[str, str]]:
    """
    Gets a list of all currently active promotions, discounts, and special offers for a specific store.
    Use this when a user asks about offers, discounts, or current promotions.

    Args:
        store_id: The ID of the store to check for promotions.
    """
    api_url = f"{BASE_URL}/data-driven-promotion/activePromotionList/Web/{store_id}/{GUEST_CUSTOMER_ID}"
    logging.info(f"Requesting active promotions for store_id '{store_id}' from: {api_url}")

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

        logging.info(f"Successfully retrieved {len(simplified_promotions)} active promotions for store_id '{store_id}'.")
        return simplified_promotions

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch active promotions for store_id '{store_id}'. Error: {e}")
        return []

def get_all_products_for_store(store_id: int) -> List[Dict[str, Any]]:
    """
    An efficient function to fetch a comprehensive list of all products available at a specific store.
    Use this for broad queries like 'What do you have in stock?', 'List all your products', or when a user wants a general overview.

    Args:
        store_id: The ID of the store for which to fetch the product list.
    """
    api_url = f"{BASE_URL}/product/productListForChatbot"
    logging.info(f"Requesting full product list for store_id '{store_id}' from: {api_url}")

    payload = {
        "store_id": str(store_id),
        "company_id": 1,
        "order_by": "popularity",
        "customer_id": GUEST_CUSTOMER_ID
    }

    try:
        response = requests.post(api_url, json=payload, timeout=20)
        response.raise_for_status()
        
        # The API returns a dictionary where the key is the store_id as a string.
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

def get_product_details(product_id: int, store_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves exhaustive details for a single product by its ID and store.
    Use this as a follow-up when a user asks for more information about a specific product found via search or category listing.

    Args:
        product_id: The unique ID of the product.
        store_id: The ID of the store to check for availability and details.
    """
    api_url = f"{BASE_URL}/product/getListOfProductDetails"
    logging.info(f"Requesting details for product_id '{product_id}' at store_id '{store_id}'.")

    payload = {
        "product_id": product_id,
        "store_id": store_id,
        "customer_id": GUEST_CUSTOMER_ID
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()

        product_data = response.json().get('data', {}).get('productData', [])

        if not product_data:
            logging.warning(f"No details found for product_id '{product_id}' at store_id '{store_id}'.")
            return None

        # Assuming the first item in the list is the product we want.
        details = product_data[0]
        
        # Simplify the response for the LLM. The raw API response for this could be very large.
        simplified_details = {
            "name": details.get("name"),
            "description": details.get("details"), # The 'details' field seems to contain rich HTML description
            "price_bdt": details.get("mrp"),
            "weight_gm": details.get("weight_in_gm"),
            "stock_quantity": details.get("stockQuantity"),
            "is_in_stock": "Yes" if details.get("stockQuantity", 0) > 0 else "No",
            "category": details.get("product_category_name"),
            "image_url": details.get("image")
        }

        logging.info(f"Successfully retrieved details for product_id '{product_id}'.")
        return simplified_details

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch details for product_id '{product_id}'. Error: {e}")
        return None