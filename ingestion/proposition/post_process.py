import pandas as pd
import json
import os
import argparse
from datetime import datetime
from loguru import logger
import sys

def process_files(csv_path: str, json_folder_path: str, output_folder_path: str):
    """
    Combines data from a CSV file and a folder of JSON files to create
    a new, consolidated set of JSON files.

    Args:
        csv_path (str): Path to the input CSV file.
        json_folder_path (str): Path to the folder containing input JSON files.
        output_folder_path (str): Path to the folder where output JSONs will be saved.
    """
    # --- 1. Initial Setup ---
    logger.info(f"Starting data processing...")
    logger.info(f"Reading CSV from: {csv_path}")
    logger.info(f"Reading JSONs from: {json_folder_path}")

    # Create the output directory if it doesn't exist
    try:
        os.makedirs(output_folder_path, exist_ok=True)
        logger.info(f"Output will be saved to: {output_folder_path}")
    except OSError as e:
        logger.error(f"Could not create output directory '{output_folder_path}': {e}")
        sys.exit(1)

    # --- 2. Load and Prepare CSV Data ---
    try:
        # Read the CSV and set 'Passage_id' as the index for fast lookups
        df = pd.read_csv(csv_path).set_index('Passage_id')
    except FileNotFoundError:
        logger.error(f"CSV file not found at path: {csv_path}")
        sys.exit(1)
    except KeyError:
        logger.error(f"The CSV file must contain a 'Passage_id' column.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred while reading the CSV: {e}")
        sys.exit(1)

    # --- 3. Process Each JSON File ---
    processed_count = 0
    for filename in os.listdir(json_folder_path):
        if not filename.endswith('.json'):
            continue

        # Extract passage_id from filename (e.g., "1.json" -> 1)
        try:
            passage_id = int(os.path.splitext(filename)[0])
        except ValueError:
            logger.warning(f"Skipping file with non-integer name: {filename}")
            continue

        # Find corresponding metadata in the DataFrame
        try:
            csv_row = df.loc[passage_id]
        except KeyError:
            logger.warning(f"No entry found in CSV for Passage_id={passage_id}. Skipping {filename}.")
            continue

        # --- 4. Read and Combine Data ---
        json_file_path = os.path.join(json_folder_path, filename)
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # Extract data from the CSV row
            topic = csv_row.get('Topic')

            # Create the list of propositions (only the 'proposition' text)
            propositions_list = [
                item.get('proposition', '') for item in json_data.get('propositions', [])
            ]

            # Create the list of summaries (Topic + 'summary' text from each proposition)
            summaries_list = [topic] + [
                item.get('summary', '') for item in json_data.get('propositions', [])
            ]

            # Construct the final JSON object
            output_data = {
                'passage_id': passage_id,
                'topic': topic,
                'text': csv_row.get('Text'),
                'date': datetime.now().isoformat(),
                'propositions': propositions_list,
                'summaries': summaries_list,
                'question_patterns': json_data.get('question_patterns', []),
                'keywords_and_phrases': json_data.get('keywords_and_phrases', [])
            }

            # --- 5. Write the New JSON File ---
            output_filepath = os.path.join(output_folder_path, filename)
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            
            processed_count += 1

        except json.JSONDecodeError:
            logger.warning(f"Could not parse JSON from {filename}. It may be corrupted. Skipping.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing {filename}: {e}")

    logger.info(f"Processing complete. Successfully generated {processed_count} JSON files.")


def main():
    """Main function to parse arguments and run the script."""
    parser = argparse.ArgumentParser(
        description="Combine data from a CSV and a folder of JSON files into a new JSON format."
    )
    parser.add_argument(
        "--csv_path",
        type=str,
        required=True,
        help="Path to the input data.csv file."
    )
    parser.add_argument(
        "--json_folder_path",
        type=str,
        required=True,
        help="Path to the folder containing the input .json files."
    )
    parser.add_argument(
        "--output_folder_path",
        type=str,
        default="output_jsons",
        help="Path to the folder where output files will be saved (default: 'output_jsons')."
    )

    args = parser.parse_args()
    process_files(args.csv_path, args.json_folder_path, args.output_folder_path)


if __name__ == "__main__":
    main()