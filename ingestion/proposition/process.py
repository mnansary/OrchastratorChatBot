# process.py
import argparse
import csv
import json
import time
from pathlib import Path
from typing import Tuple, Dict, Any

from loguru import logger
from tqdm import tqdm

# Import the necessary components from your other modules
from llm import call_llm
from prompt import create_prompt, generation_config
from utils import save_dict_to_json

# --- Configuration for Retry Logic ---
MAX_RETRIES = 10
MIN_WAIT_SECONDS = 15  # Start with a slightly longer wait
MAX_WAIT_SECONDS = 600 # Cap wait time at 5 minutes

def process_single_passage(
    row_data: Dict[str, Any],
    output_dir: Path
) -> Tuple[str, str]:
    """
    Processes a single passage to generate and save its propositions.

    Includes logic to skip existing files and retry on failure with exponential backoff.

    Args:
        row_data (Dict[str, Any]): A dictionary containing all data for one passage row.
        output_dir (Path): The directory to save the output JSON file.

    Returns:
        A tuple containing the final status ('SUCCESS', 'SKIPPED', 'FAILED')
        and a message (output path on success, error details on failure).
    """
    # Use 'Passage_id' or 'passage_id' for flexibility
    passage_id = row_data.get('Passage_id') or row_data.get('passage_id')
    if not passage_id:
        return "FAILED", "Row is missing a 'Passage_id' or 'passage_id' column."

    output_path = output_dir / f"{passage_id}.json"

    # 1. Skip if the file already exists to allow for easy resuming
    if output_path.exists():
        logger.info(f"Skipping Passage ID {passage_id}: Output JSON already exists.")
        return "SKIPPED", ""

    # 2. Create the specialized prompt for this passage
    try:
        prompt = create_prompt(row_data)
    except ValueError as e:
        return "FAILED", f"Could not create prompt for {passage_id}. Error: {e}"

    # 3. Start the retry loop for robustness against transient API errors
    for attempt in range(MAX_RETRIES):
        logger.info(f"Processing Passage ID {passage_id} (Attempt {attempt + 1}/{MAX_RETRIES})...")
        
        try:
            # Call the LLM to get the structured proposition data
            response_text = call_llm(prompt, generation_config)

            if not response_text:
                raise ValueError("LLM returned an empty or None response.")

            # Validate that the response is valid JSON
            proposition_data = json.loads(response_text)
            
            # Save the successfully generated and validated data
            save_dict_to_json(proposition_data, output_path)
            
            # If all steps succeed, return success and exit the retry loop
            return "SUCCESS", str(output_path)

        except (json.JSONDecodeError, ValueError, RuntimeError) as e:
            logger.warning(f"Attempt {attempt + 1} failed for Passage ID {passage_id}. Error: {e}")
            
            if attempt == MAX_RETRIES - 1:
                # Last attempt failed, so break to the failure case
                break

            # Implement exponential backoff with jitter to avoid thundering herd issues
            wait_time = min(MAX_WAIT_SECONDS, MIN_WAIT_SECONDS * (2 ** attempt))
            logger.info(f"Waiting for {wait_time:.2f} seconds before next retry...")
            time.sleep(wait_time)

    # 4. If the loop finishes without a success return, it's a permanent failure for this item
    error_message = f"Failed to process Passage ID {passage_id} after {MAX_RETRIES} attempts."
    logger.error(error_message)
    return "FAILED", error_message


def main():
    """
    Main function to parse arguments and process a CSV of passages.
    """
    parser = argparse.ArgumentParser(
        description="Process a CSV of passages to generate Proposition JSON files using an LLM.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        required=True,
        help="Path to the input CSV file. Must contain at least 'Passage_id' and 'Text' columns."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Path to the directory where the output .json files and error.csv will be saved."
    )
    args = parser.parse_args()

    # --- Setup Directories and Paths ---
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # --- Read Input CSV ---
    try:
        with open(args.input_csv, mode='r', encoding='utf-8-sig') as f: # Use utf-8-sig to handle potential BOM
            passages_to_process = list(csv.DictReader(f))
        
        if not passages_to_process or not ('Passage_id' in passages_to_process[0] or 'passage_id' in passages_to_process[0]):
             raise KeyError("CSV must contain a 'Passage_id' or 'passage_id' column.")
        if not 'Text' in passages_to_process[0] and not 'passage' in passages_to_process[0]:
             raise KeyError("CSV must contain a 'Text' or 'passage' column.")
             
    except FileNotFoundError:
        logger.error(f"Input CSV file not found at: {args.input_csv}")
        return
    except KeyError as e:
        logger.error(f"Missing required column in CSV file: {e}")
        return
    except Exception as e:
        logger.error(f"Failed to read or parse input CSV. Error: {e}")
        return

    logger.info(f"Found {len(passages_to_process)} passages to process from {args.input_csv}")

    # --- Setup Error Logging and Counters ---
    error_log_path = args.output_dir / "error_log.csv"
    success_count, skipped_count, failed_count = 0, 0, 0

    # --- Main Processing Loop ---
    with open(error_log_path, 'w', newline='', encoding='utf-8') as error_log_file:
        error_writer = csv.writer(error_log_file)
        error_writer.writerow(['passage_id', 'error_message'])

        for row in tqdm(passages_to_process, desc="Processing Passages"):
            status, message = process_single_passage(row, args.output_dir)

            if status == "SUCCESS":
                success_count += 1
            elif status == "SKIPPED":
                skipped_count += 1
            elif status == "FAILED":
                failed_count += 1
                passage_id = row.get('Passage_id') or row.get('passage_id', 'UNKNOWN_ID')
                error_writer.writerow([passage_id, message])

    # --- Final Summary Report ---
    total_files = len(passages_to_process)
    
    print("\n" + "="*30)
    logger.info("Processing Complete.")
    print(f"Total Passages in CSV: {total_files}")
    print(f"Successfully Processed: {success_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print(f"Failed (after all retries): {failed_count}")
    print(f"Output JSONs are saved in: {args.output_dir.resolve()}")
    if failed_count > 0:
        print(f"Details for failed passages saved in: {error_log_path.resolve()}")
    print("="*30)


if __name__ == "__main__":
    main()