# --- START OF MODIFIED FILE: cogops/utils/private_api.py ---

import os
import requests
import logging
from typing import Dict, Any, Optional

# --- NEW: Import tenacity for robust retry logic ---
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# --- Configuration ---
BASE_URL = os.getenv("COMPANY_API_BASE_URL")

# --- NEW: Define the exception type that should trigger a retry ---
# REASON: We only want to retry on network-level failures, not on HTTP
# client or server errors (like 4xx or 5xx), which are handled separately.
RETRYABLE_EXCEPTIONS = (requests.exceptions.RequestException,)

# --- NEW: Define a logging function for tenacity to use before retrying ---
def log_private_api_retry_attempt(retry_state):
    """Logs a warning message before a retry attempt for the private API."""
    # Extract the endpoint from the function's arguments for a more informative log.
    endpoint = retry_state.args[0] if retry_state.args else "unknown_endpoint"
    logging.warning(
        f"Private API call to '{endpoint}' failed with {retry_state.outcome.exception()}, "
        f"retrying in {retry_state.next_action.sleep} seconds... "
        f"(Attempt {retry_state.attempt_number})"
    )

# --- CRITICAL CHANGE: Added retry decorator ---
# REASON: Makes all internal API calls resilient to transient network failures,
# improving the reliability of all tools that depend on this function.
@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    before_sleep=log_private_api_retry_attempt
)
def make_private_request(endpoint: str, session_meta: Dict[str, Any], method: str = 'GET', payload: Optional[Dict] = None) -> Optional[Dict]:
    """
    Handles authenticated requests by sending both access and refresh tokens in the headers.
    This function is now hardened with automatic retries for network errors.
    """
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
            # Should not happen, but good practice to handle.
            logging.error(f"Unsupported HTTP method '{method}' for make_private_request.")
            return None
            
        # This will raise an HTTPError for 4xx or 5xx responses.
        # The retry logic will NOT catch this, which is the desired behavior.
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        # Log specific HTTP errors (e.g., 401 Unauthorized, 404 Not Found, 500 Server Error)
        # These are not retried because the problem is not transient.
        logging.error(f"HTTP error for {endpoint}: {e} - Response: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        # This block will now only be hit if the retry attempts are exhausted.
        logging.error(f"Request failed for {endpoint} after multiple retries: {e}")
        # Re-raise the exception to be handled by the tenacity decorator.
        raise

# --- END OF MODIFIED FILE: cogops/utils/private_api.py ---