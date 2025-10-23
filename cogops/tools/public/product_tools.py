# FILE: tools/public/product_tools.py

import os
import requests
from bs4 import BeautifulSoup
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


def _fetch_and_build_product_tree(store_id: int, customer_id: str) -> Dict[str, Any]:
    """
    Internal function to fetch product data and build a structured Python dictionary.
    This is the shared logic for both Markdown and YAML formatters.
    """
    api_url = f"{BASE_URL}/product/productListForChatbot"
    payload = {
        "store_id": str(store_id), "company_id": 1, "order_by": "popularity", "customer_id": str(customer_id)
    }

    try:
        response = requests.post(api_url, json=payload, timeout=20)
        response.raise_for_status()
        product_list = response.json().get('data', {}).get(str(store_id), [])
        if not product_list:
            return {}

        product_tree = {}
        for product in product_list:
            required_keys = ['parent_category_slug', 'parent_category_name', 'category_slug', 'category_name', 'product_slug', 'name']
            if not all(product.get(key) for key in required_keys):
                continue
            
            parent_slug = product['parent_category_slug']
            if parent_slug not in product_tree:
                product_tree[parent_slug] = {
                    "name": product['parent_category_name'], "slug": parent_slug, "categories": {}
                }
            
            cat_slug = product['category_slug']
            if cat_slug not in product_tree[parent_slug]["categories"]:
                product_tree[parent_slug]["categories"][cat_slug] = {
                    "name": product['category_name'], "slug": cat_slug, "products": []
                }
            
            product_tree[parent_slug]["categories"][cat_slug]["products"].append({
                "name": product["name"], "slug": product["product_slug"]
            })
        
        # Convert inner category dicts to lists
        for parent_data in product_tree.values():
            parent_data["categories"] = list(parent_data["categories"].values())

        return {"store_name": product_list[0].get('store_name'), "tree": product_tree}

    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed for store_id '{store_id}'. Error: {e}")
        return {}
    except (ValueError, KeyError) as e:
        logging.error(f"Failed to parse API response for store_id '{store_id}'. Error: {e}")
        return {}

def get_product_catalog_as_markdown(store_id: int, customer_id: str) -> str:
    """
    Fetches the product catalog and formats it as a highly token-efficient 
    and human-readable Markdown string. It uses the [Name](slug) syntax.

    Returns:
        A Markdown formatted string of the product catalog.
    """
    data = _fetch_and_build_product_tree(store_id, customer_id)
    if not data or not data.get("tree"):
        return "No products are currently available for this store."

    product_tree = data["tree"]
    store_name = data["store_name"]

    markdown_lines = [f"# Product Catalog for {store_name}\n"]
    for parent_data in product_tree.values():
        # Parent Category: Level 2 Heading
        markdown_lines.append(f"## [{parent_data['name']}]({parent_data['slug']})")
        for category_data in parent_data['categories']:
            # Category: Level 3 Heading
            markdown_lines.append(f"  ### [{category_data['name']}]({category_data['slug']})")
            for prod in category_data['products']:
                # Product: List item
                markdown_lines.append(f"    - [{prod['name']}]({prod['slug']})")
        markdown_lines.append("") # Spacer

    return "\n".join(markdown_lines)

def get_product_details_as_markdown(slug: str, store_id: int, customer_id: int) -> str:
    """
    Retrieves exhaustive details for a single product using its slug and formats
    the output into a token-efficient, LLM-friendly Markdown string.

    Args:
        slug: The URL-friendly slug of the product (e.g., 'beef-back-leg-bone-in').
        store_id: The ID of the store for checking availability and details.
        customer_id: The customer's ID. This is required (e.g., '369' for a guest).

    Returns:
        A detailed Markdown string about the product, or an error message string.
    """
    api_url = f"{BASE_URL}/product/getListOfProductDetails"
    
    logging.info(f"Requesting details for slug '{slug}' at store_id '{store_id}' for customer '{customer_id}'.")

    payload = {
        "slug": slug,
        "store_id": str(store_id),
        "customer_id": str(customer_id) # Ensure customer_id is a string for the JSON payload
    }

    try:
        response = requests.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        api_data = response.json().get('data', {})

        product_data = api_data.get('productData')
        if not product_data or not product_data[0]:
            logging.warning(f"No details found for slug '{slug}' at store_id '{store_id}'.")
            return f"Sorry, I could not find any details for a product with the identifier '{slug}'."

        main_product = product_data[0]
        markdown_lines = []

        # --- Main Product Section ---
        markdown_lines.append(f"# {main_product.get('name', 'Product Details')}")

        # Price & Availability
        markdown_lines.append("\n**Price & Availability**")
        price_unit = f"{main_product.get('sale_uom', '')} {main_product.get('sal_uom_name', '')}".strip()
        markdown_lines.append(f"- **Price:** {main_product.get('mrp', 'N/A')} BDT per {price_unit}")
        
        stock_qty = main_product.get('temp_quantity', 0)
        markdown_lines.append(f"- **Availability:** {'In Stock' if stock_qty > 0 else 'Out of Stock'}")
        
        # Discount Information
        discount_value = main_product.get('discount_value', 0)
        if discount_value > 0:
            # Now, determine the type of discount to format the string correctly.
            if main_product.get('discount_type') == 'Amount':
                # This handles fixed amount discounts.
                markdown_lines.append(f"- **Current Offer:** {discount_value} TK off!")
            else:
                # This handles 'Percent' and any other potential discount types as a percentage.
                markdown_lines.append(f"- **Current Offer:** {discount_value}% off!")

        # Product Description
        markdown_lines.append("\n**Description**")
        details_html = main_product.get('details', 'No description available.')
        cleaned_details = BeautifulSoup(details_html, "html.parser").get_text(separator='\n', strip=True)
        markdown_lines.append(cleaned_details)

        # Promotional Info
        if main_product.get('meta_description'):
            markdown_lines.append("\n**Good to Know**")
            markdown_lines.append(f"> {main_product['meta_description']}")

        # --- Related Products Section (Top 3) ---
        related_products = api_data.get('relatedProducts', [])[:3]
        if related_products:
            markdown_lines.append("\n---\n\n## Frequently Bought Together")
            for rel_prod in related_products:
                markdown_lines.append(f"\n### {rel_prod.get('name', 'Related Product')}")
                rel_price_unit = f"{rel_prod.get('sale_uom', '')} {rel_prod.get('sal_uom_name', '')}".strip()
                rel_stock = "In Stock" if rel_prod.get('temp_quantity', 0) > 0 else "Out of Stock"
                markdown_lines.append(f"- **Price:** {rel_prod.get('mrp')} BDT per {rel_price_unit}")
                markdown_lines.append(f"- **Availability:** {rel_stock}")
                markdown_lines.append(f"- **Identifier:** `{rel_prod.get('slug')}`")

        return "\n".join(markdown_lines)

    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed for product slug '{slug}'. Error: {e}")
        return "Sorry, I'm having trouble connecting to the product server right now."
    except (KeyError, IndexError) as e:
        logging.error(f"Failed to parse the API response for slug '{slug}'. Missing key: {e}")
        return "Sorry, I received an unexpected response from the server."