import pandas as pd
from google import genai
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from loguru import logger
import os 


class ApiKeyManager:
    """
    Manages a pool of API keys with strict cooldown and rate-limiting rules.

    This manager implements the following logic:
    1.  Lazy Client Instantiation: It manages keys, not pre-loaded clients.
        A `genai.Client` is created just-in-time when a key is dispatched.
    2.  Round-Robin Selection: It cycles through available keys.
    3.  Per-Key Cooldown (Rule #3): After a key is used, it becomes unavailable
        for a specified duration (default: 30 minutes).
    4.  Global Cooldown (Rule #4): After any key is used, the manager enforces
        a system-wide wait period (default: 60 seconds) before another key
        can be dispatched.
    """

    def __init__(
        self,
        api_key_csv_path: str,
        key_cooldown_seconds: int = 60,  # 30 minutes
        global_cooldown_seconds: int = 5,   # 60 seconds
    ):
        """
        Initializes the ApiKeyManager.

        Args:
            api_key_csv_path (str): Path to the CSV file containing API keys.
                                    The CSV must have a header named 'api'.
            key_cooldown_seconds (int): Cooldown period for an individual key after use.
            global_cooldown_seconds (int): System-wide cooldown after any API call.
        """
        if not os.path.exists(api_key_csv_path):
            raise FileNotFoundError(f"API key file not found at: {api_key_csv_path}")
            
        self.api_keys: List[str] = pd.read_csv(api_key_csv_path)["api"].dropna().tolist()
        if not self.api_keys:
            raise ValueError("No API keys found in the provided CSV file.")

        logger.info(f"Loaded {len(self.api_keys)} API keys.")

        self.key_cooldown = timedelta(seconds=key_cooldown_seconds)
        self.global_cooldown = timedelta(seconds=global_cooldown_seconds)

        # Tracks the last time each specific key was used
        self.key_last_used: Dict[str, datetime] = {}
        # Tracks the last time *any* key was used for the global cooldown
        self.last_global_call_time: Optional[datetime] = None
        
        # Round-robin starting index
        self.index = 0

    def get_client(self):
        """
        Finds an available API key, enforces cooldowns, and returns a new `genai.Client`.

        This method will block and wait if cooldowns are in effect.

        Returns:
            A `genai.Client` instance configured with an available API key.

        Raises:
            RuntimeError: If no keys are available even after waiting.
        """
        # no.4: Enforce the 60-second global cooldown first
        if self.last_global_call_time:
            elapsed_since_last_call = datetime.now() - self.last_global_call_time
            if elapsed_since_last_call < self.global_cooldown:
                wait_time = (self.global_cooldown - elapsed_since_last_call).total_seconds()
                logger.info(f"Global 60s cooldown in effect. Waiting for {wait_time:.2f} seconds.")
                time.sleep(wait_time)

        # Loop indefinitely until we find a key. This handles the case where all keys
        # might be on cooldown and we need to wait.
        while True:
            # no.2: Cycle through keys to find an available one
            num_keys = len(self.api_keys)
            
            # We check every key starting from the current round-robin index
            for i in range(num_keys):
                current_index = (self.index + i) % num_keys
                key = self.api_keys[current_index]
                
                last_used = self.key_last_used.get(key)
                
                # no.3: Check if the key's 30-minute cooldown has passed
                if not last_used or (datetime.now() - last_used) > self.key_cooldown:
                    logger.success(f"Found available key at index {current_index}.")
                    
                    # Update state *before* returning the client
                    now = datetime.now()
                    self.key_last_used[key] = now
                    self.last_global_call_time = now
                    
                    # Update the round-robin index for the *next* search
                    self.index = (current_index + 1) % num_keys
                    
                    # Create the client just-in-time
                    logger.info(f"Creating and returning client for key ending in '...{key[-4:]}'.")
                    return genai.Client(api_key=key)

            # If the loop completes, all keys are currently on cooldown
            self._wait_for_next_available_key()


    def _wait_for_next_available_key(self):
        """
        A helper method to calculate the minimum wait time until the next key
        becomes available, and then sleeps for that duration.
        """
        now = datetime.now()
        
        # Find the earliest time a key will be free
        earliest_available_time = min(
            last_used + self.key_cooldown
            for key, last_used in self.key_last_used.items()
            if key in self.api_keys
        )
        
        wait_duration = (earliest_available_time - now).total_seconds()
        
        if wait_duration > 0:
            logger.warning(
                f"All {len(self.api_keys)} keys are on 30-min cooldown. "
                f"Waiting for {wait_duration:.2f} seconds for the next key to become available."
            )
            time.sleep(wait_duration)


# --- Factory Function and Example Usage ---

def create_client_manager(csv_path: str):
    """
    Factory function to create an instance of the ApiKeyManager.
    This replaces the old `create_wrapped_clients_google`.
    """
    return ApiKeyManager(api_key_csv_path=csv_path)