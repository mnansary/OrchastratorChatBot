# FILE: cogops/context_manager.py (New File)

import logging
from cogops.tools.public.product_tools import get_product_catalog_as_markdown
from cogops.tools.public.location_tools import generate_location_and_delivery_markdown

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ContextManager:
    """
    A singleton-like class to generate and hold global, static context strings
    that are expensive to create and rarely change (e.g., on server restart).
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        # This ensures only one instance of ContextManager ever exists.
        if not cls._instance:
            cls._instance = super(ContextManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # The __init__ might be called multiple times, but we only want to initialize once.
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.location_context: str = ""
        self.store_catalog: str = ""
        self._initialized = True
        logging.info("ContextManager initialized.")

    def build_static_context(self, store_id: int, customer_id: str):
        """
        Calls the necessary functions to generate the static Markdown contexts.
        This should be run once at application startup by the main API service.
        
        Args:
            store_id: A default or primary store_id to generate the initial catalog.
            customer_id: A guest customer_id for generating the initial catalog.
        """
        logging.info("Building static context: Fetching locations and product catalog...")
        
        # 1. Generate Location & Delivery Info Markdown
        # This function calls multiple APIs and combines them into one string.
        self.location_context = generate_location_and_delivery_markdown()
        if not self.location_context:
            logging.error("CRITICAL: Failed to build location context!")
            self.location_context = "# Location Information\n\n*Error: Could not retrieve location data.*"

        # 2. Generate Store Product Catalog Markdown
        # This function calls the product list API and formats it.
        self.store_catalog = get_product_catalog_as_markdown(store_id=store_id, customer_id=customer_id)
        if not self.store_catalog:
            logging.error("CRITICAL: Failed to build store catalog context!")
            self.store_catalog = "# Store Catalog\n\n*Error: Could not retrieve product catalog.*"

        logging.info("✅ Static context build complete. The application is ready.")

# Create a single instance that will be imported and used by other parts of the application.
context_manager = ContextManager()