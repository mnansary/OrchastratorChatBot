# FILE: tools/public/location_tools.py (or a new utility file)

import os
import requests
import logging
from typing import List, Dict, Any
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL", "https://api.bengalmeat.com") # Provide a default
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Existing API Call Functions (keep them as they are) ---

def get_all_store_locations() -> List[Dict[str, Any]]:
    """Fetches a list of all physical Bengal Meat stores."""
    api_url = f"{BASE_URL}/store/storelistopen/1?is_visible=1"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch store locations: {e}")
        return []

def get_operational_cities() -> List[str]:
    """Returns a list of all cities where Bengal Meat operates."""
    api_url = f"{BASE_URL}/customer/city"
    try:
        response = requests.post(api_url, timeout=10)
        response.raise_for_status()
        cities_data = response.json().get('data', {}).get('data', [])
        return [city['name'] for city in cities_data if 'name' in city]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch operational cities: {e}")
        return []

def get_all_delivery_areas() -> List[Dict[str, Any]]:
    """Fetches a list of all specific delivery areas."""
    api_url = f"{BASE_URL}/polygon/areaByCity/"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch delivery areas: {e}")
        return []

# --- NEW MASTER FUNCTION ---

def generate_location_and_delivery_markdown() -> str:
    """
    Fetches data from all location-related APIs and combines it into a single,
    comprehensive, and LLM-friendly Markdown document.

    This is designed to be run periodically to generate a static context file.
    """
    logging.info("Starting generation of the master location Markdown document...")

    # 1. Fetch all necessary data from the APIs
    stores = get_all_store_locations()
    areas = get_all_delivery_areas()

    if not stores:
        return "# Location Information\n\nSorry, could not retrieve store location information at this time."

    # 2. Process and structure the data
    # Group stores by city
    stores_by_city = defaultdict(list)
    for store in stores:
        # Filter out test stores or stores without a city
        if "test" in store.get("name", "").lower() or not store.get("CITY"):
            continue
        stores_by_city[store["CITY"]].append(store)

    # Map delivery areas to their respective stores for easy lookup
    areas_by_store_id = defaultdict(list)
    for area in areas:
        if area.get("storeId") and area.get("name"):
            areas_by_store_id[area["storeId"]].append(area["name"])

    # 3. Build the Markdown String
    markdown_lines = ["# Bengal Meat Store Locations & Delivery Areas"]
    markdown_lines.append("This document contains all operational cities, physical store details, and specific delivery areas.")

    # Sort cities for consistent output
    sorted_cities = sorted(stores_by_city.keys())

    for city in sorted_cities:
        markdown_lines.append(f"\n## City: {city}")
        
        # Sort stores within the city by name
        sorted_stores = sorted(stores_by_city[city], key=lambda s: s['name'])
        
        for store in sorted_stores:
            store_id = store['id']
            markdown_lines.append(f"\n### {store.get('name', 'N/A')}")
            markdown_lines.append(f"- **Store ID:** {store_id}")
            markdown_lines.append(f"- **Address:** {store.get('address', 'N/A').strip()}")
            markdown_lines.append(f"- **Phone:** {store.get('contact_person_phone', 'N/A')}")
            
            # Add the list of delivery areas for this store
            delivery_areas = sorted(areas_by_store_id.get(store_id, []))
            if delivery_areas:
                markdown_lines.append("- **Delivery Areas Covered:**")
                for area in delivery_areas:
                    markdown_lines.append(f"  - {area}")

    logging.info("Successfully generated the master location Markdown document.")
    return "\n".join(markdown_lines)