# FILE: cogops/tools/tools.py

from typing import List, Dict, Any

# --- Absolute imports for all tool functions ---
from cogops.tools.custom.knowledge_retriever import retrieve_knowledge, get_current_time
from cogops.tools.public.location_tools import get_all_store_locations, get_operational_cities, get_all_delivery_areas
from cogops.tools.public.product_tools import list_product_categories, get_products_by_category, search_products
from cogops.tools.public.promotions_and_details import get_active_promotions, get_all_products_for_store, get_product_details
from cogops.tools.private.user_tools import fetch_user_profile, fetch_user_loyalty_status
from cogops.tools.private.order_tools import fetch_user_order_history, fetch_order_contents
from cogops.tools.private.checkout_tools import fetch_user_saved_addresses, fetch_delivery_slots, fetch_payment_options

# --- Available Tools Map ---
# This dictionary maps the function name (as the LLM will call it) to the actual Python function object.
available_tools_map = {
    # Public & Custom Tools
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
    # Private, Context-Enrichment Tools
    "fetch_user_profile": fetch_user_profile,
    "fetch_user_loyalty_status": fetch_user_loyalty_status,
    "fetch_user_order_history": fetch_user_order_history,
    "fetch_order_contents": fetch_order_contents,
    "fetch_user_saved_addresses": fetch_user_saved_addresses,
    "fetch_delivery_slots": fetch_delivery_slots,
    "fetch_payment_options": fetch_payment_options,
}


# --- OpenAI-Compatible Tools List (Schemas) ---
# This list defines the schema for each tool, which the LLM uses to understand what the tool does,
# what parameters it needs, and what kind of output to expect.
tools_list = [
    # ===================================================================
    # CUSTOM & KNOWLEDGE TOOLS
    # ===================================================================
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": (
                "When to call: Use for any non-product, non-location, or non-promotion questions. This includes company policy, FAQs, how-to guides, delivery processes, payment inquiries, return policies, and questions about food safety or Halal processes.\n"
                "Expected Output: A list of dictionaries, where each dictionary is a relevant text passage from the knowledge base.\n"
                "Example Output: [{'passage_id': 2, 'topic': 'রিটার্ন ও রিফান্ড নীতি', 'text': 'যেহেতু পণ্যসমূহ দ্রুত নষ্ট হয়ে যায়... ডেলিভারি কর্মী উপস্থিত থাকা অবস্থায় জানাতে হবে...'}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The specific question or topic to search for, e.g., 'return policy' or 'how long is delivery'."}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": (
                "When to call: Use ONLY when the user explicitly asks for the current time or date.\n"
                "Expected Output: A single string containing the current date and time.\n"
                "Example Output: '2025-10-26 14:30:00'"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # ===================================================================
    # PUBLIC LOCATION TOOLS
    # ===================================================================
    {
        "type": "function",
        "function": {
            "name": "get_all_store_locations",
            "description": (
                "When to call: Use when a user asks for 'store addresses', 'physical shops', 'butcher shop locations', 'outlet contact numbers', or 'where are your stores?'.\n"
                "Expected Output: A list of dictionaries, each representing a physical store with its name, address, phone number, and city.\n"
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
                "When to call: Use to answer questions like 'Which cities do you operate in?', 'Are you available in Chittagong?', or 'Where do you deliver?'.\n"
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

    # ===================================================================
    # PUBLIC PRODUCT & PROMOTION TOOLS (Session-Aware)
    # ===================================================================
    {
        "type": "function",
        "function": {
            "name": "list_product_categories",
            "description": (
                "When to call: Use for broad questions about product types, like 'What do you sell?' or 'What kinds of meat do you have?'.\n"
                "Expected Output: A list of strings, showing the category name and its 'slug' for potential follow-up tool calls.\n"
                "Example Output: ['Beef (slug: beef)', 'Mutton (slug: mutton)', 'Fish (slug: fish)', 'Snacks (slug: snacks)']"
            ),
            "parameters": { "type": "object", "properties": {}, "required": [] }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_products_by_category",
            "description": (
                "When to call: Use when a user wants to browse a whole category, like 'show me all your beef items' or 'What chicken items are available?'.\n"
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
                "When to call: Use when a user searches for a specific item by name, like 'Do you have t-bone steak?' or 'find burger patty'.\n"
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
    {
        "type": "function",
        "function": {
            "name": "get_active_promotions",
            "description": (
                "When to call: Use when a user asks about 'offers', 'discounts', 'deals', or 'promotions'. Can return personalized promotions for logged-in users.\n"
                "Expected Output: A list of dictionaries, each describing an active promotion.\n"
                "Example Output: [{'promotion_name': '5 protein Snacks offer oct 25', 'description': '', ...}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "integer", "description": "The user's currently selected store ID."},
                    "session_meta": {"type": "object", "description": "The user's complete session data, including user_id if they are logged in."}
                },
                "required": ["store_id", "session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_products_for_store",
            "description": (
                "When to call: Use for very broad queries like 'What's in stock today?', 'List all your products'. Provides a full inventory overview. Can return personalized prices for logged-in users.\n"
                "Expected Output: A comprehensive list of product dictionaries for each item in the store.\n"
                "Example Output: [{'product_id': 140, 'name': 'Beef Pepperoni', 'category': 'Cold Cuts', 'price_bdt': 320, ...}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "integer", "description": "The user's currently selected store ID."},
                    "session_meta": {"type": "object", "description": "The user's complete session data, including user_id if they are logged in."}
                },
                "required": ["store_id", "session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "When to call: Use as a follow-up for more information about a *specific product*. Provides full details and personalized price for logged-in users. Does not include image data.\n"
                "Expected Output: A single dictionary with detailed product information.\n"
                "Example Output: {'name': 'Beef T-Bone Steak', 'description': 'Carved from Hindquarter...', 'price_bdt': 1020, ...}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "The unique ID of the product to look up."},
                    "store_id": {"type": "integer", "description": "The user's currently selected store ID."},
                    "session_meta": {"type": "object", "description": "The user's complete session data, including user_id if they are logged in."}
                },
                "required": ["product_id", "store_id", "session_meta"]
            }
        }
    },

    # ===================================================================
    # PRIVATE, CONTEXT-ENRICHMENT TOOLS (FOR LOGGED-IN USERS)
    # ===================================================================
    {
        "type": "function",
        "function": {
            "name": "fetch_user_profile",
            "description": (
                "When to call: [AUTONOMOUS] Call this automatically at the start of a session for a logged-in user to understand who they are.\n"
                "Purpose: Fetches the user's name, email, city, etc., to personalize the conversation.\n"
                "Expected Output: A dictionary with user profile details.\n"
                "Example Output: {'name': 'MO MO', 'email': 'momo@gmail.com', 'city': 'Dhaka'}"
            ),
            "parameters": {
                "type": "object",
                "properties": {"session_meta": {"type": "object", "description": "The user's session data containing user_id and access_token."}},
                "required": ["session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_user_loyalty_status",
            "description": (
                "When to call: [AUTONOMOUS] Call this at the start of a session for a logged-in user.\n"
                "Purpose: To know the user's loyalty points and balance for potential personalized offers.\n"
                "Expected Output: A dictionary with the user's points and balance.\n"
                "Example Output: {'points': 0, 'balance': 0}"
            ),
            "parameters": {
                "type": "object",
                "properties": {"session_meta": {"type": "object", "description": "The user's session data containing the access_token."}},
                "required": ["session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_user_order_history",
            "description": (
                "When to call: [AUTONOMOUS] Call this at the start of a session for a logged-in user.\n"
                "Purpose: To understand the user's past purchase habits for making relevant product suggestions.\n"
                "Expected Output: A list of dictionaries, each summarizing a past order.\n"
                "Example Output: [{'order_id': 33772, 'order_code': '25081411552764833049', 'order_date': '2025-08-14T05:55:27.000Z', 'status': 'Pending'}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {"session_meta": {"type": "object", "description": "The user's session data containing the access_token."}},
                "required": ["session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_order_contents",
            "description": (
                "When to call: Use this when a logged-in user refers to a specific past order by its ID or date, especially regarding a complaint or a question about its contents like 'What was in my last order?'.\n"
                "Purpose: To get the exact items from a past order to provide detailed support.\n"
                "Expected Output: A dictionary containing order summary and a list of products.\n"
                "Example Output: {'order_summary': {...}, 'products_in_order': [{'name': 'Butter Chicken- Cooked', 'quantity': 1}]}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "The unique ID of the order to investigate."},
                    "session_meta": {"type": "object", "description": "The user's session data containing the access_token."}
                },
                "required": ["order_id", "session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_user_saved_addresses",
            "description": (
                "When to call: Use when a logged-in user expresses intent to order or asks about delivery, to proactively suggest their saved addresses.\n"
                "Purpose: To confirm delivery locations without making the user type their address again.\n"
                "Expected Output: A list of saved address dictionaries.\n"
                "Example Output: [{'name': 'Md Moshiur Rahman', 'address_details': 'House 10, Road 02, Dhanmondi, Dhaka', 'phone': ''}]"
            ),
            "parameters": {
                "type": "object",
                "properties": {"session_meta": {"type": "object", "description": "The user's session data containing user_id and access_token."}},
                "required": ["session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_delivery_slots",
            "description": (
                "When to call: Use when a logged-in user is in the checkout process or asks 'When can I get my delivery?'.\n"
                "Purpose: To provide real-time, available delivery time slots for a specific date.\n"
                "Expected Output: A list of available time slot strings.\n"
                "Example Output: ['10:00 AM - 12:00 PM', '04:00 PM - 06:00 PM']"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "The date to check in YYYY-MM-DD format."},
                    "session_meta": {"type": "object", "description": "The user's session data containing the access_token."}
                },
                "required": ["date", "session_meta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_payment_options",
            "description": (
                "When to call: Use when a user is about to checkout or asks 'How can I pay?'.\n"
                "Purpose: To list all currently enabled payment methods.\n"
                "Expected Output: A list of payment method names.\n"
                "Example Output: ['Online Payment', 'Cash on delivery']"
            ),
            "parameters": {
                "type": "object",
                "properties": {"session_meta": {"type": "object", "description": "The user's session data containing the access_token."}},
                "required": ["session_meta"]
            }
        }
    }
]