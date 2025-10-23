# FILE: tools/private/order_tools.py

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
            response = requests.get(api_url, headers=headers, timeout=15)
        elif method == 'POST':
            response = requests.post(api_url, headers=headers, json=payload, timeout=15)
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


def fetch_user_order_history(session_meta: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Fetches the user's past order history for the agent's internal context."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_user_order_history: Attempted to call without user_id. Skipping.")
        return None

    endpoint = "order-btoc/orderHistoryOrderData/0"
    logging.info(f"Fetching order history for user_id: {user_id}")
    data = _make_private_request(endpoint, session_meta)
    
    if data and 'data' in data:
        orders = data['data']
        simplified_history = [
            {
                "order_id": order.get("id"), "order_code": order.get("order_code"),
                "order_date": order.get("order_at"), "total_amount": order.get("grand_total"),
                "status": order.get("status")
            }
            for order in orders[:5]
        ]
        logging.info(f"Successfully fetched {len(simplified_history)} recent orders for user_id: {user_id}")
        return simplified_history

    logging.warning(f"Failed to fetch or parse order history for user_id: {user_id}")
    return None


def fetch_order_contents(order_id: int, session_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetches the specific products that were part of a single past order."""
    user_id = session_meta.get('user_id')
    if not user_id:
        logging.warning("fetch_order_contents: Attempted to call without user_id. Skipping.")
        return None

    endpoint = f"order-btoc/orderProductListFromOrderId/{order_id}"
    logging.info(f"Fetching contents for order_id: {order_id}")
    data = _make_private_request(endpoint, session_meta)
    
    if data and data.get('data', {}).get('orderInfo') and data.get('data', {}).get('baseProductData'):
        order_info = data['data']['orderInfo']
        products = data['data']['baseProductData']
        
        order_details = {
            "order_summary": {
                "order_code": order_info.get("order_code"), "order_date": order_info.get("order_at"),
                "status": order_info.get("status"), "total_amount": order_info.get("grand_total")
            },
            "products_in_order": [
                {"name": prod.get("product_name"), "quantity": prod.get("quantity"), "price_per_unit": prod.get("rate")}
                for prod in products
            ]
        }
        logging.info(f"Successfully fetched {len(products)} items for order_id: {order_id}")
        return order_details
        
    logging.warning(f"Failed to fetch or parse contents for order_id: {order_id}")
    return None