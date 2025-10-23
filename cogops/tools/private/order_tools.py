# FILE: tools/private/order_tools.py

import os
import requests
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from datetime import datetime
from cogops.utils.private_api import make_private_request as _make_private_request
load_dotenv()

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL")
if not BASE_URL:
    raise ValueError("FATAL ERROR: COMPANY_API_BASE_URL environment variable is not set.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper to format dates cleanly ---
def _format_date(date_string: Optional[str]) -> str:
    if not date_string:
        return "N/A"
    try:
        return datetime.fromisoformat(date_string.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return date_string

# --- NEW MASTER TOOL FUNCTION ---

def get_user_order_profile_as_markdown(session_meta: Dict[str, Any], order_code: Optional[str] = None) -> str:
    """
    Fetches a user's order history and/or the details of a specific order,
    then formats the output into a comprehensive and token-efficient Markdown string.

    - If 'order_code' is provided, it fetches details for that specific order.
    - If 'order_code' is omitted, it fetches a summary of the user's 3 most recent orders.
    """
    user_id = session_meta.get('user_id')
    if not user_id:
        return "Error: Cannot fetch order profile without a user session."

    # --- Step 1: Always fetch the recent order history first ---
    history_endpoint = "order-btoc/orderHistoryOrderData/0"
    history_response = _make_private_request(history_endpoint, session_meta)

    if not history_response or not history_response.get('data'):
        return "# User Order Profile\n\nNo order history found for this user."

    order_history = history_response['data']

    # --- Scenario A: User asked for a SPECIFIC order ---
    if order_code:
        target_order_summary = next((order for order in order_history if order.get("order_code") == order_code), None)
        if not target_order_summary:
            return f"# Order Not Found\n\nCould not find an order with the code `{order_code}` in the user's recent history."

        order_id = target_order_summary.get('id')
        return _fetch_and_format_single_order(order_id, session_meta)

    # --- Scenario B: User asked for a GENERAL history or for recommendations ---
    else:
        markdown_lines = ["# User Order Profile", "A summary of the user's most recent purchasing behavior."]
        
        # Limit to the 3 most recent orders to avoid being too slow or verbose
        for order_summary in order_history[:3]:
            order_id = order_summary.get('id')
            if order_id:
                # Fetch details for each order to get the product list
                details_md = _fetch_and_format_single_order(order_id, session_meta, summary_mode=True)
                markdown_lines.append("\n---\n" + details_md)
        
        return "\n".join(markdown_lines)


def _fetch_and_format_single_order(order_id: int, session_meta: Dict[str, Any], summary_mode: bool = False) -> str:
    """Internal helper to fetch and format one order's details into Markdown."""
    endpoint = f"order-btoc/orderProductListFromOrderId/{order_id}"
    data = _make_private_request(endpoint, session_meta)

    if not data or not data.get('data'):
        return f"### Order ID: {order_id}\n- Error: Could not retrieve details for this order."

    order_info = data['data'].get('orderInfo', {})
    products = data['data'].get('baseProductData', [])

    if not order_info:
        return f"### Order ID: {order_id}\n- Error: Missing order summary information."
        
    order_code = order_info.get('order_code', 'N/A')
    order_date = _format_date(order_info.get('order_at'))
    status = order_info.get('status', 'N/A')

    # In summary mode, we use a more compact format
    if summary_mode:
        lines = [f"### Order `{order_code}` (Placed on: {order_date})"]
        lines.append(f"- **Status:** {status}")
        lines.append(f"- **Total:** {order_info.get('grand_total', 'N/A')} BDT")
    else: # Full detail mode
        lines = [f"# Details for Order `{order_code}`"]
        lines.append(f"- **Status:** {status}")
        lines.append(f"- **Order Date:** {order_date}")
        lines.append(f"- **Payment Method:** {order_info.get('online_payment_method', 'N/A')}")
        lines.append(f"- **Delivery Address:** {order_info.get('delivery_address_text', 'N/A')}")
        lines.append(f"- **Subtotal:** {order_info.get('total', 'N/A')} BDT")
        lines.append(f"- **Delivery Fee:** {order_info.get('delivery_charge', 'N/A')} BDT")
        lines.append(f"- **Grand Total:** {order_info.get('grand_total', 'N/A')} BDT")

    if products:
        lines.append("- **Items in Order:**")
        for prod in products:
            lines.append(f"  - {prod.get('product_name', 'N/A')} (Qty: {prod.get('quantity', 0)})")
    else:
        lines.append("- No product information available for this order.")
        
    return "\n".join(lines)