# FILE: tests/test_tools.py

import asyncio
import os
import json
import logging
import argparse
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

# --- Pre-run Setup ---
# Load environment variables from the .env file in the project root.
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Tool Imports (All public and private tools) ---
from cogops.tools.custom.knowledge_retriever import retrieve_knowledge, get_current_time
from cogops.tools.public.location_tools import get_all_store_locations, get_operational_cities, get_all_delivery_areas
from cogops.tools.public.product_tools import list_product_categories, get_products_by_category, search_products
from cogops.tools.public.promotions_and_details import get_active_promotions, get_all_products_for_store, get_product_details
from cogops.tools.private.user_tools import fetch_user_profile, fetch_user_loyalty_status
from cogops.tools.private.order_tools import fetch_user_order_history, fetch_order_contents
from cogops.tools.private.checkout_tools import fetch_user_saved_addresses, fetch_delivery_slots, fetch_payment_options


def json_date_serializer(obj):
    """JSON serializer for date/datetime objects that are not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# --- Test Data Constants ---
TEST_CATEGORY_SLUG = "beef"
TEST_SEARCH_QUERY = "keema"
TEST_PRODUCT_ID = 4 # Beef Bone In
TEST_KNOWLEDGE_QUERY = "রিটার্ন পলিসি কি?"
TEST_ORDER_ID = 33772 # An example order ID from your Postman collection
TEST_DELIVERY_DATE = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')


async def run_test(tool_name: str, tool_function, *args, **kwargs) -> bool:
    """A helper function to run a single tool test, print the output, and return its status."""
    print("\n" + "="*80)
    print(f"▶️  TESTING: {tool_name}")
    print("="*80)
    
    try:
        if asyncio.iscoroutinefunction(tool_function):
            result = await tool_function(*args, **kwargs)
        else:
            result = tool_function(*args, **kwargs)
        
        print("✅ SUCCESS! Tool executed.")
        print("--- OUTPUT ---")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=json_date_serializer))
        print("--- END OF OUTPUT ---")
        return True

    except Exception as e:
        print(f"❌ FAILED! An error occurred during the test for '{tool_name}'.")
        logging.error(f"Error details: {e}", exc_info=True)
        return False

async def main(session_meta_path: str):
    """Main function to orchestrate all tool tests using session metadata."""
    print("🚀 STARTING BENGAL MEAT API TOOLCHAIN VERIFICATION (with Session Meta) 🚀")
    
    # --- Load Session Metadata ---
    try:
        with open(session_meta_path, 'r') as f:
            session_meta = json.load(f)
        # Ensure correct data types from JSON strings
        session_meta['user_id'] = int(session_meta['user_id'])
        session_meta['store_id'] = int(session_meta['store_id'])
        print(f"✅ Successfully loaded session metadata for user_id: {session_meta['user_id']}")
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"\n❌ FATAL ERROR: Could not load or parse the session_meta JSON file. Please check the path and content. Error: {e}")
        return

    passed_tests = []
    failed_tests = []

    # --- UPDATED: A comprehensive list of all public and private tool tests ---
    all_tests = [
        # --- Custom & RAG Tools ---
        ("Get Current Time", get_current_time, [], {}),
        ("Retrieve Knowledge (RAG)", retrieve_knowledge, [TEST_KNOWLEDGE_QUERY], {}),
        
        # --- Public Location Tools ---
        ("Get All Store Locations", get_all_store_locations, [], {}),
        ("Get Operational Cities", get_operational_cities, [], {}),
        ("Get All Delivery Areas", get_all_delivery_areas, [], {}),
        
        # --- Public Product Tools ---
        ("List Product Categories", list_product_categories, [], {}),
        ("Search Products", search_products, [TEST_SEARCH_QUERY], {}),
        ("Get Products by Category", get_products_by_category, [], {'category_slug': TEST_CATEGORY_SLUG, 'store_id': session_meta['store_id']}),
        
        # --- Public Session-Aware Tools ---
        ("Get Active Promotions", get_active_promotions, [], {'store_id': session_meta['store_id'], 'session_meta': session_meta}),
        ("Get All Products for Store", get_all_products_for_store, [], {'store_id': session_meta['store_id'], 'session_meta': session_meta}),
        ("Get Product Details", get_product_details, [], {'product_id': TEST_PRODUCT_ID, 'store_id': session_meta['store_id'], 'session_meta': session_meta}),

        # --- Private User Tools ---
        ("Fetch User Profile", fetch_user_profile, [session_meta], {}),
        ("Fetch User Loyalty Status", fetch_user_loyalty_status, [session_meta], {}),
        
        # --- Private Order Tools ---
        ("Fetch User Order History", fetch_user_order_history, [session_meta], {}),
        ("Fetch Order Contents", fetch_order_contents, [TEST_ORDER_ID, session_meta], {}),

        # --- Private Checkout Tools ---
        ("Fetch User Saved Addresses", fetch_user_saved_addresses, [session_meta], {}),
        ("Fetch Delivery Slots", fetch_delivery_slots, [TEST_DELIVERY_DATE, session_meta], {}),
        ("Fetch Payment Options", fetch_payment_options, [session_meta], {}),
    ]

    for name, func, args, kwargs in all_tests:
        success = await run_test(name, func, *args, **kwargs)
        if success:
            passed_tests.append(name)
        else:
            failed_tests.append(name)

    # --- Final Summary ---
    total_tests = len(all_tests)
    total_passed = len(passed_tests)
    total_failed = len(failed_tests)

    print("\n" + "#"*80)
    print("🏁 TOOLCHAIN VERIFICATION COMPLETE 🏁")
    print("#"*80)
    print(f"\nSUMMARY: Total Tests: {total_tests} | ✅ Passed: {total_passed} | ❌ Failed: {total_failed}\n")

    if passed_tests:
        print("--- ✅ PASSED TESTS ---")
        for test_name in passed_tests:
            print(f"  - {test_name}")
    
    if failed_tests:
        print("\n--- ❌ FAILED TESTS ---")
        for test_name in failed_tests:
            print(f"  - {test_name}")
        print("\nReview the logs above for error details on the failed tests.")
    
    print("\n" + "#"*80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a comprehensive test suite for all public and private chatbot tools.")
    parser.add_argument(
        '--session_meta',
        type=str,
        required=True,
        help='Path to the JSON file containing session metadata (access_token, refresh_token, user_id, store_id).'
    )
    args = parser.parse_args()
    
    if not os.getenv("COMPANY_API_BASE_URL"):
        print("\n❌ FATAL ERROR: 'COMPANY_API_BASE_URL' is not set in your .env file. Please set it and try again.")
    else:
        asyncio.run(main(args.session_meta))