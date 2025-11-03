# FILE: cogops/tools/tools.py

from typing import List, Dict, Any

# --- Absolute imports for all tool functions ---
from cogops.tools.custom.knowledge_retriever import retrieve_knowledge
from cogops.tools.public.product_tools import get_product_details_as_markdown
from cogops.tools.private.order_tools import get_user_order_profile_as_markdown
from cogops.tools.public.promotions_tools import get_promotional_products

# --- Available Tools Map ---
# This dictionary maps the function name (the "key") to the actual Python function object (the "value").
# The "key" MUST EXACTLY MATCH the 'name' field in the schemas below.
available_tools_map = {
    # Public & Custom Tools
    "retrieve_knowledge": retrieve_knowledge,
    "get_product_details_as_markdown": get_product_details_as_markdown,
    
    # Private, Context-Enrichment Tools (require a valid user session)
    "get_user_order_profile_as_markdown": get_user_order_profile_as_markdown,
    # --- NEW: Add the promotional products tool to the map ---
    "get_promotional_products": get_promotional_products,
}


# --- OpenAI-Compatible Tools List (Schemas) ---
# This list defines the schema for each tool. The LLM uses this to understand:
# 1. What the tool does (from the description).
# 2. What to call it (from the 'name' field, which links to the map above).
# 3. What arguments it needs (from the parameters).
tools_list = [
    # ===================================================================
    # CUSTOM & KNOWLEDGE TOOLS
    # ===================================================================
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": "Call this function to find answers in the official Bengal Meat knowledge base for all informational, non-product, and non-order questions. It retrieves relevant text passages to answer the user's query.\n\n*** USE THIS TOOL FOR QUESTIONS ABOUT ***\n1.  **Policies & Rules:** Return/Refund Policy, Privacy Policy, Terms and Conditions.\n2.  **How-To Guides:** How to place an order, track an order, use coupons, reset passwords.\n3.  **Product & Safety Info:** Food safety, Halal process, product details (e.g., 'what is a steak?'), sourcing.\n4.  **General Company Info:** Delivery times/charges, payment methods, customer care hours, business inquiries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's full and specific question. Use the text from the user's prompt directly. EXAMPLES: 'ফেরত দেওয়ার নিয়ম কী?' (What is the return policy?), 'আমার অর্ডার ট্র্যাক করব কীভাবে?' (How do I track my order?)."
                    }
                },
                "required": ["query"]
            }
        }
    },

    # ===================================================================
    # PUBLIC PRODUCT TOOLS (Session-Aware)
    # ===================================================================
    {
        "type": "function",
        "function": {
            # --- FIX 1: The 'name' now EXACTLY matches the key in available_tools_map ---
            "name": "get_product_details_as_markdown",
            "description": "Call this function to get ALL details for a SINGLE, SPECIFIC product. Use this when a user asks for more information about a product they are interested in.\n\n*** WHEN TO USE ***\n- The user asks for the price of a specific item, e.g., 'What is the price of Beef Bone In?'\n- The user asks if a specific item is in stock, e.g., 'Is Chinigura Rice available?'\n- The user asks for a description of a specific item, e.g., 'Tell me more about the Chicken Nuggets.'\n\n*** CRITICAL INSTRUCTION FOR FINDING THE 'slug' ***\nBefore calling this tool, you MUST find the product's unique `slug` from the `STORE_CATALOG` that is provided in your system prompt. Match the user's requested product name to the name in the catalog to find its corresponding slug. **Do not guess the slug.**\n\n*** WHAT IT RETURNS ***\n- A **Markdown formatted string** with a complete summary of the product, including price, stock status, description, and related product suggestions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "The unique URL-friendly identifier for the product, found in the STORE_CATALOG. Example: 'beef-back-leg-bone-in', 'paratha-20-pcs'."
                    },
                    "store_id": {
                        "type": "integer",
                        "description": "The unique numerical ID of the store where the user is shopping. This is mandatory."
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "The customer's unique ID. This is REQUIRED. If the user is not logged in, you MUST use the default guest ID, which is '369'."
                    }
                },
                "required": ["slug", "store_id", "customer_id"]
            }
        }
    },
    # ===================================================================
    # PRODUCT DISCOVERY & PROMOTIONAL TOOLS
    # ===================================================================
    {
        "type": "function",
        "function": {
            "name": "get_promotional_products",
            "description": "Use this tool to answer user questions about product recommendations, deals, popular items, or best-selling products. It can fetch multiple categories at once. This is the main tool for product discovery questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categories": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["best_sellers", "best_deals", "popular_items"]
                        },
                        "description": "A list of categories to fetch. Use the category that best matches the user's query. For example, if the user asks 'What's on sale?', use ['best_deals']. If they ask 'What do you recommend?', a good default is ['best_sellers', 'popular_items']."
                    }
                },
                "required": ["categories"]
            }
        }
    },
    
    # ===================================================================
    # PRIVATE, ORDER-RELATED TOOLS (FOR LOGGED-IN USERS)
    # ===================================================================
    {
        "type": "function",
        "function": {
            # --- FIX 2: The 'name' now EXACTLY matches the key in available_tools_map ---
            "name": "get_user_order_profile_as_markdown",
            "description": "The main tool for answering ANY question about a logged-in user's past or current orders.\n\n*** WHEN TO USE ***\n\n1.  **For a Specific Order:** If the user provides an order number/code (e.g., 'What's the status of order 250814...?'), call this function and pass the code to the `order_code` parameter.\n\n2.  **For General History:** If the user asks a general question (e.g., 'Show my recent orders', 'What did I buy last time?'), call this function WITHOUT the `order_code` parameter.\n\n*** WHAT IT RETURNS ***\n- A **Markdown formatted string** summarizing the user's recent orders or detailing a specific one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_code": {
                        "type": "string",
                        "description": "Optional. The unique code of a specific order (e.g., '25081411552764833049'). Provide this ONLY when the user asks about one single order. For general history questions, OMIT this parameter."
                    }
                }
            }
        }
    }
]