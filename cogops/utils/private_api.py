# FILE: cogops/utils/private_api.py (NEW FILE)

import os
import requests
import logging
from typing import Dict, Any, Optional

BASE_URL = os.getenv("COMPANY_API_BASE_URL")

def make_private_request(endpoint: str, session_meta: Dict[str, Any], method: str = 'GET', payload: Optional[Dict] = None) -> Optional[Dict]:
    """Handles authenticated requests by sending both access and refresh tokens in the headers."""
    access_token = session_meta.get('access_token')
    refresh_token = session_meta.get('refresh_token')

    if not all([access_token, refresh_token]):
        logging.error(f"Missing auth tokens for private API call to {endpoint}.")
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "refreshToken": refresh_token,
        "Content-Type": "application/json"
    }
    api_url = f"{BASE_URL}/{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(api_url, headers=headers, timeout=15)
        elif method == 'POST':
            response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        else:
            return None
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error for {endpoint}: {e} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed for {endpoint}: {e}")
        return None