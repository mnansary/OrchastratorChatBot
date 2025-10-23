# FILE: tools/public/product_tools.py

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


def list_product_categories() -> List[str]:
    """
    Retrieves the main categories of products available (e.g., Beef, Mutton, Fish).
    Use this when a user asks 'What kind of products do you sell?' or 'What are your product categories?'.
    """
    api_url = f"{BASE_URL}/product-category/listbytype/B2C"
    logging.info(f"Requesting product categories from: {api_url}")

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        data = response.json().get('data', [])
        
        # Extract just the category names for a clean list. The 'slug' is also useful for other tool calls.
        categories = [
            f"{category.get('name')} (slug: {category.get('slug')})"
            for category in data if category.get('name')
        ]

        logging.info(f"Successfully retrieved {len(categories)} product categories.")
        return categories

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch product categories. Error: {e}")
        return []


def get_products_by_category(category_slug: str, store_id: int) -> List[Dict[str, Any]]:
    """
    Fetches all available products within a specific category for a given store.
    Use this when a user wants to see all items in a category, for example, 'Show me all your beef products' or 'What mutton items do you have?'.

    Args:
        category_slug: The URL-friendly slug for the category (e.g., 'beef', 'mutton', 'snacks').
        store_id: The ID of the store to check for product availability.
    """
    api_url = f"{BASE_URL}/product/productListByCategoryForB2C"
    logging.info(f"Requesting products for category '{category_slug}' at store '{store_id}' from: {api_url}")

    payload = {
        "store_id": store_id,
        "slug": category_slug,
        "company_id": 1,
        "order_by": "popularity"
    }

    try:
        response = requests.post(api_url, json=payload, timeout=15)
        response.raise_for_status()

        data = response.json().get('data', {})
        all_products = []
        # The data is structured as a dictionary where keys are sub-categories. We need to iterate through them.
        for sub_category in data.values():
            for product in sub_category:
                all_products.append({
                    "name": product.get("name"),
                    "price_bdt": product.get("mrp"),
                    "weight_gm": product.get("weight_in_gm"),
                    "stock_quantity": product.get("stockQuantity"),
                    "is_in_stock": "Yes" if product.get("stockQuantity", 0) > 0 else "No"
                })

        logging.info(f"Successfully retrieved {len(all_products)} products for category '{category_slug}'.")
        return all_products

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch products for category '{category_slug}'. Error: {e}")
        return []


def search_products(query: str) -> List[Dict[str, str]]:
    """
    Performs a keyword search across the product catalog to find specific items.
    Use this when a user is looking for a specific product by name, like 'Do you have beef keema?' or 'search for sausages'.

    Args:
        query: The user's search term.
    """
    api_url = f"{BASE_URL}/search/keySearch"
    logging.info(f"Searching for products with query: '{query}'")

    payload = {"key": query}

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()

        products = response.json()
        
        # Simplify the output for the LLM
        simplified_results = [
            {
                "product_id": product.get("id"),
                "name": product.get("name"),
                "category": product.get("category_name")
            }
            for product in products
        ]

        logging.info(f"Found {len(simplified_results)} products for query '{query}'.")
        return simplified_results

    except requests.exceptions.RequestException as e:
        logging.error(f"Product search failed for query '{query}'. Error: {e}")
        return []