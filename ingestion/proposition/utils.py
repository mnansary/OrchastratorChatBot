# utils.py
import json
from pathlib import Path
from loguru import logger
from typing import Dict, Any

def save_dict_to_json(data: Dict[str, Any], file_path: Path):
    """
    Saves a dictionary to a JSON file with UTF-8 encoding.

    Creates the parent directory if it does not exist.

    Args:
        data (Dict[str, Any]): The dictionary to save.
        file_path (Path): The output JSON file path.
    
    Raises:
        IOError: If there is an issue writing to the file.
        Exception: For other potential errors during directory creation or JSON serialization.
    """
    try:
        # Ensure the parent directory exists before attempting to write the file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open the file and write the JSON data
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        logger.success(f"Successfully saved data to {file_path}")
        
    except IOError as e:
        logger.error(f"Failed to write to file {file_path}. Error: {e}")
        # Re-raise the exception to be caught by the main processing loop
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving JSON to {file_path}. Error: {e}")
        # Re-raise for visibility in the main loop
        raise