# --- START OF REWRITTEN FILE: cogops/tools/public/promotions_tools.py ---

import os
import requests
import logging
from typing import List, Dict, Any, Optional, Union

# Use the hardened private_api utility for authenticated calls
from cogops.utils.private_api import make_private_request

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL")
if not BASE_URL:
    raise ValueError("FATAL ERROR: COMPANY_API_BASE_URL environment variable is not set.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _format_products_to_markdown(data: Dict[str, List[Dict]], categories: List[str], limit: int = 5) -> str:
    """
    Internal helper to format the raw API product data into a clean, token-efficient
    Markdown string for the LLM.

    Args:
        data (Dict[str, List[Dict]]): The raw data dict from the API ('bestSell', 'bestDeal', etc.).
        categories (List[str]): The list of categories to include in the output.
        limit (int): The maximum number of products to list per category.

    Returns:
        str: A formatted Markdown string.
    """
    markdown_lines = []
    
    # Map the tool's category names to the API's response keys
    key_map = {
        "best_sellers": "bestSell",
        "best_deals": "bestDeal",
        "popular_items": "popular"
    }

    for category in categories:
        api_key = key_map.get(category)
        product_list = data.get(api_key)

        if not product_list:
            continue

        # Use a more user-friendly title in the Markdown output
        title = category.replace('_', ' ').title()
        markdown_lines.append(f"## Top {limit} {title}")
        
        for product in product_list[:limit]:
            name = product.get('name', 'N/A')
            price = product.get('mrp', 'N/A')
            slug = product.get('slug', '')
            
            line = f"- **{name}**: {price} BDT"
            
            # Add discount information if it's relevant and valid
            discount_value = product.get('discount_value', 0)
            if discount_value > 0 and product.get('discount_validity', 0) == 1:
                discount_type = product.get('discount_type', 'Percent')
                if discount_type == 'Amount':
                    line += f" (Discount: {discount_value} TK off!)"
                else:
                    line += f" (Discount: {discount_value}%)"
            
            # Add the slug for the LLM to use with other tools
            line += f" `slug: {slug}`"
            markdown_lines.append(line)
        
        markdown_lines.append("") # Add a spacer between categories

    if not markdown_lines:
        return "No items were found in the requested categories for this store."
        
    return "\n".join(markdown_lines)


def get_promotional_products(
    session_meta: Dict[str, Any],
    categories: Union[str, List[str]] = ["best_sellers", "best_deals", "popular_items"]
) -> str:
    """
    Fetches and summarizes products from 'Best Sellers', 'Best Deals', or 'Popular' categories.

    This tool intelligently detects if a user is logged in to provide potentially
    personalized results. The output is a formatted Markdown string suitable for an LLM.

    Args:
        session_meta (Dict[str, Any]): The user's session data from the API service.
        categories (Union[str, List[str]]): A list of categories to fetch.
            Valid options are: "best_sellers", "best_deals", "popular_items".
            Defaults to all three.

    Returns:
        str: A Markdown formatted string summarizing the requested product categories.
    """
    store_id = session_meta.get('store_id')
    if not store_id:
        return "Error: store_id is missing from the session."

    # Standardize categories to a list
    if isinstance(categories, str):
        categories = [categories]

    # Determine if this is a private (logged-in) or public (guest) call
    customer_id = session_meta.get('user_id')
    access_token = session_meta.get('access_token')
    is_private_call = all([customer_id, access_token])

    api_data = None
    try:
        if is_private_call:
            # Use the personalized endpoint for logged-in users
            endpoint = f"product/bestSellBestDealPopular/{store_id}/{customer_id}"
            logging.info(f"Making a PRIVATE request to promotional endpoint: {endpoint}")
            response_json = make_private_request(endpoint, session_meta)
        else:
            # Use the public endpoint for guests
            endpoint = f"product/bestSellBestDealPopular/{store_id}"
            api_url = f"{BASE_URL}/{endpoint}"
            logging.info(f"Making a PUBLIC request to promotional endpoint: {api_url}")
            response = requests.get(api_url, timeout=15)
            response.raise_for_status()
            response_json = response.json()
        
        api_data = response_json.get('data') if response_json else None

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching promotional products for store {store_id}: {e}")
        return f"Error: The server returned an error: {e.response.status_code}"
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error fetching promotional products for store {store_id}: {e}")
        return "Error: Could not connect to the product server."
    except Exception as e:
        logging.error(f"An unexpected error occurred in get_promotional_products: {e}", exc_info=True)
        return "Error: An unexpected error occurred while fetching product data."

    if not api_data:
        logging.warning(f"No promotional data returned from API for store {store_id}.")
        return "No best sellers, deals, or popular items could be found at this time."

    # Format the successfully fetched data into Markdown for the LLM
    return _format_products_to_markdown(api_data, categories)

# --- END OF REWRITTEN FILE: cogops/tools/public/promotions_tools.py ---