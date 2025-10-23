# FILE: tools/public/location_tools.py

import os
import requests
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from your .env file
load_dotenv()

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_all_store_locations() -> List[Dict[str, str]]:
    """
    Fetches a list of all physical Bengal Meat stores and butcher shops.
    Use this when a user asks for store locations, addresses, or contact numbers.
    """
    api_url = f"{BASE_URL}/store/storelistopen/1?is_visible=1"
    logging.info(f"Requesting all store locations from: {api_url}")

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()  # Will raise an exception for 4xx/5xx status codes

        data = response.json().get('data', [])

        # Simplify the output for the LLM, providing only essential information.
        simplified_stores = [
            {
                "name": store.get("name"),
                "address": store.get("address"),
                "phone_number": store.get("contact_person_phone"),
                "city": store.get("CITY")
            }
            for store in data
        ]

        logging.info(f"Successfully retrieved {len(simplified_stores)} store locations.")
        return simplified_stores

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch store locations. Error: {e}")
        return []


def get_operational_cities() -> List[str]:
    """
    Returns a list of all cities where Bengal Meat operates.
    Use this to answer questions like 'Which cities do you operate in?' or 'Are you available in Dhaka?'.
    """
    api_url = f"{BASE_URL}/customer/city"
    logging.info(f"Requesting operational cities from: {api_url}")

    try:
        # According to the Postman collection, this is a POST request with an empty body.
        response = requests.post(api_url, timeout=10)
        response.raise_for_status()

        # The city list is nested within the response data.
        cities_data = response.json().get('data', {}).get('data', [])
        
        # Extract just the names for a clean, simple list.
        city_names = [city['name'] for city in cities_data if 'name' in city]

        logging.info(f"Successfully retrieved {len(city_names)} operational cities.")
        return city_names

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch operational cities. Error: {e}")
        return []


def get_all_delivery_areas() -> List[str]:
    """
    Fetches a list of all specific neighborhoods and areas where Bengal Meat provides delivery.
    Use this to check for delivery availability in a particular area like 'Gulshan' or 'Mohammadpur'.
    """
    api_url = f"{BASE_URL}/polygon/areaByCity/"
    logging.info(f"Requesting all delivery areas from: {api_url}")

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        data = response.json().get('data', [])
        
        # Format the output as "Area, City" for clarity.
        area_list = [
            f"{area.get('name', 'N/A')}, {area.get('city_name', 'N/A')}" 
            for area in data
        ]

        logging.info(f"Successfully retrieved {len(area_list)} delivery areas.")
        return area_list

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch delivery areas. Error: {e}")
        return []