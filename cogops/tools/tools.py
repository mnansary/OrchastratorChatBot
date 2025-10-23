# FILE: cogops/tools/tools.py

from typing import List, Dict, Any

# --- Absolute imports for all tool functions ---
from cogops.tools.custom.knowledge_retriever import retrieve_knowledge, get_current_time
from cogops.tools.public.location_tools import get_all_store_locations, get_operational_cities, get_all_delivery_areas
from cogops.tools.public.product_tools import list_product_categories, get_products_by_category, search_products
from cogops.tools.public.promotions_and_details import get_active_promotions, get_all_products_for_store, get_product_details


# --- Available Tools Map ---
# This dictionary maps the function name (as the LLM will call it) to the actual Python function object.
available_tools_map = {
    "retrieve_knowledge": retrieve_knowledge,
    "get_current_time": get_current_time,
    "get_all_store_locations": get_all_store_locations,
    "get_operational_cities": get_operational_cities,
    "get_all_delivery_areas": get_all_delivery_areas,
    "list_product_categories": list_product_categories,
    "get_products_by_category": get_products_by_category,
    "search_products": search_products,
    "get_active_promotions": get_active_promotions,
    "get_all_products_for_store": get_all_products_for_store,
    "get_product_details": get_product_details,
}


# --- OpenAI-Compatible Tools List (Schemas) ---
# This list defines the schema for each tool, which the LLM uses to understand what the tool does,
# what parameters it needs, and what kind of output to expect.
tools_list = [
    # --- Custom Tools ---
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": (
                "When to call: Use this for any non-product, non-location, or non-promotion questions. "
                "This includes company policy, FAQs, how-to guides, delivery times, payment methods, "
                "return policies, and questions about food safety or Halal processes.\n"
                "Expected Output: A list of dictionaries, where each dictionary is a relevant text passage from the knowledge base.\n"
                "Example Output: [{'passage_id': 2, 'topic': 'রিটার্ন ও রিফান্ড নীতি', 'text': 'যেহেতু পণ্যসমূহ দ্রুত নষ্ট হয়ে যায়... ডেলিভারি কর্মী উপস্থিত থাকা অবস্থায় জানাতে হবে...'}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The specific question or topic to search for, e.g., 'return policy' or 'how long is delivery'."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": (
                "When to call: Use this when the user explicitly asks for the current time or date.\n"
                "Expected Output: A single string containing the current date and time.\n"
                "Example Output: '2025-10-26 14:30:00'"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # --- Public Location Tools ---
    {
        "type": "function",
        "function": {
            "name": "get_all_store_locations",
            "description": (
                "When to call: Use when a user asks for store addresses, physical shop locations, butcher shop contact numbers, or outlet details.\n"
                "Expected Output: A list of dictionaries, where each dictionary represents a physical store with its name, address, phone number, and city.\n"
                "Example Output: [{'name': 'Gourmet Butcher Shop Dhanmondi-27', 'address': 'House-21/B, Road-16 (New), Dhanmondi 27', 'phone_number': '01871006433', 'city': 'Dhaka'}]"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_operational_cities",
            "description": (
                "When to call: Use to answer questions about which cities Bengal Meat operates in, for example, 'Are you available in Chittagong?' or 'Which cities do you deliver to?'.\n"
                "Expected Output: A simple list of city names where the service is available.\n"
                "Example Output: ['Dhaka', 'Chittagong', 'Sylhet', 'Khulna']"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_delivery_areas",
            "description": (
                "When to call: Use to check for delivery availability in a specific neighborhood or area, such as 'Do you deliver to Gulshan?' or 'Is Banani a delivery area?'.\n"
                "Expected Output: A list of strings, with each string formatted as 'Area, City'.\n"
                "Example Output: ['Gulshan-1, Dhaka', 'Banani, Dhaka', 'Adabor, Dhaka']"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # --- Public Product Tools ---
    {
        "type": "function",
        "function": {
            "name": "list_product_categories",
            "description": (
                "When to call: Use for broad questions about product types, like 'What do you sell?' or 'What kinds of meat do you have?'.\n"
                "Expected Output: A list of strings, showing the category name and its 'slug', which is useful for other tool calls.\n"
                "Example Output: ['Beef (slug: beef)', 'Mutton (slug: mutton)', 'Fish (slug: fish)', 'Snacks (slug: snacks)']"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_products_by_category",
            "description": (
                "When to call: Use when a user wants to browse a whole category, like 'Show me all your beef products' or 'What chicken items are available?'.\n"
                "Expected Output: A list of product dictionaries with key details like name, price, weight, and stock status.\n"
                "Example Output: [{'name': 'Beef Bone In', 'price_bdt': 860, 'weight_gm': 1000, 'stock_quantity': 11, 'is_in_stock': 'Yes'}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category_slug": {"type": "string", "description": "The URL-friendly slug for the category, e.g., 'beef', 'mutton'."},
                    "store_id": {"type": "integer", "description": "The user's currently selected store ID."}
                },
                "required": ["category_slug", "store_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "When to call: Use when a user searches for a specific item by name, like 'Do you have T-bone steak?' or 'search for chicken nuggets'.\n"
                "Expected Output: A list of product dictionaries with the product's ID, name, and category. The ID is crucial for follow-up questions.\n"
                "Example Output: [{'product_id': 112, 'name': 'Beef T-Bone Steak', 'category': 'Special Cuts'}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The user's search term for the product."}},
                "required": ["query"]
            }
        }
    },

    # --- Public Promotions & Details Tools ---
    {
        "type": "function",
        "function": {
            "name": "get_active_promotions",
            "description": (
                "When to call: Use when a user asks about 'offers', 'discounts', 'deals', or 'promotions'.\n"
                "Expected Output: A list of dictionaries, each describing an active promotion with its name, description, and validity dates.\n"
                "Example Output: [{'promotion_name': '5 protein Snacks offer oct 25', 'description': '', 'validity_start_date': '2025-09-30T18:00:00.000Z', 'validity_end_date': '2025-10-30T18:00:00.000Z'}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {"store_id": {"type": "integer", "description": "The user's currently selected store ID."}},
                "required": ["store_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_products_for_store",
            "description": (
                "When to call: Use for very broad queries like 'What's in stock today?', 'List all your products', or 'What do you have?'. This provides a full inventory overview for the selected store.\n"
                "Expected Output: A comprehensive list of product dictionaries containing essential details for each item in the store.\n"
                "Example Output: [{'product_id': 140, 'name': 'Beef Pepperoni', 'category': 'Cold Cuts', 'price_bdt': 320, 'is_in_stock': 'Yes', 'has_discount': 'Yes'}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {"store_id": {"type": "integer", "description": "The user's currently selected store ID."}},
                "required": ["store_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "When to call: Use this as a follow-up when a user asks for more information about a *specific product* that has already been identified (e.g., by a product search). This provides the full product description.\n"
                "Expected Output: A single dictionary containing detailed information about the requested product, or null if not found.\n"
                "Example Output: {'name': 'Beef T-Bone Steak', 'description': 'Carved from Hindquarter...', 'price_bdt': 1020, 'weight_gm': 300, 'is_in_stock': 'Yes', ...}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "The unique ID of the product to look up."},
                    "store_id": {"type": "integer", "description": "The user's currently selected store ID."}
                },
                "required": ["product_id", "store_id"]
            }
        }
    }
]