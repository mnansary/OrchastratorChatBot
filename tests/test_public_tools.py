# FILE: tests/test_tools.py

import asyncio
import os
import json
import logging
from dotenv import load_dotenv

# --- Pre-run Setup ---
# Load environment variables from the .env file in the project root.
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Tool Imports (using absolute paths from the project root) ---
from cogops.tools.custom.knowledge_retriever import retrieve_knowledge, get_current_time
from cogops.tools.public.location_tools import get_all_store_locations, get_operational_cities, get_all_delivery_areas
from cogops.tools.public.product_tools import list_product_categories, get_products_by_category, search_products
from cogops.tools.public.promotions_and_details import get_active_promotions, get_all_products_for_store, get_product_details

# Add this with your other imports
from datetime import date, datetime

# Add this helper function after the imports
def json_date_serializer(obj):
    """JSON serializer for date/datetime objects that are not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# --- Test Data Constants ---
# Using a known, valid store_id from the Postman collection for reliable testing.
TEST_STORE_ID = 37  # Bengal Meat Butcher Shop Mohammadpur
TEST_CATEGORY_SLUG = "beef"
TEST_SEARCH_QUERY = "keema"
TEST_PRODUCT_ID = 4 # Beef Bone In
TEST_KNOWLEDGE_QUERY = "রিটার্ন পলিসি কি?"


async def run_test(tool_name: str, tool_function, *args, **kwargs) -> bool:
    """
    A helper function to run a single tool test, print the output, and return its status.
    Returns True for success and False for failure.
    """
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
        # Use the custom serializer to handle date objects
        print(json.dumps(result, indent=2, ensure_ascii=False, default=json_date_serializer))
        print("--- END OF OUTPUT ---")
        return True

    except Exception as e:
        print(f"❌ FAILED! An error occurred during the test for '{tool_name}'.")
        logging.error(f"Error details: {e}", exc_info=True)
        return False

async def main():
    """Main function to orchestrate all tool tests and provide a final summary."""
    print("🚀 STARTING BENGAL MEAT API TOOLCHAIN VERIFICATION 🚀")
    print("This script will call each tool function to verify API connectivity and data parsing.")

    if not os.getenv("COMPANY_API_BASE_URL"):
        print("\n❌ FATAL ERROR: 'COMPANY_API_BASE_URL' is not set in your .env file. Please set it and try again.")
        return

    passed_tests = []
    failed_tests = []

    # A list of all tests to run, containing the name, function, and arguments.
    all_tests = [
        ("Get Current Time", get_current_time, [], {}),
        ("Retrieve Knowledge (RAG)", retrieve_knowledge, [TEST_KNOWLEDGE_QUERY], {}),
        ("Get All Store Locations", get_all_store_locations, [], {}),
        ("Get Operational Cities", get_operational_cities, [], {}),
        ("Get All Delivery Areas", get_all_delivery_areas, [], {}),
        ("List Product Categories", list_product_categories, [], {}),
        ("Search Products", search_products, [TEST_SEARCH_QUERY], {}),
        ("Get Products by Category", get_products_by_category, [], {'category_slug': TEST_CATEGORY_SLUG, 'store_id': TEST_STORE_ID}),
        ("Get Active Promotions", get_active_promotions, [TEST_STORE_ID], {}),
        ("Get All Products for Store (Chatbot API)", get_all_products_for_store, [TEST_STORE_ID], {}),
        ("Get Product Details", get_product_details, [], {'product_id': TEST_PRODUCT_ID, 'store_id': TEST_STORE_ID}),
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
    asyncio.run(main())