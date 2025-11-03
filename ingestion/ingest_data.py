# --- START OF MODIFIED FILE: ingestion/ingest_data.py ---

import os
import yaml
import argparse
import json
from datetime import datetime
from loguru import logger
import sys
from dotenv import load_dotenv
from tqdm import tqdm
import chromadb

# --- Custom Module Imports ---
from cogops.retriver.db import SQLDatabaseManager
from cogops.utils.db_config import get_postgres_config
from cogops.models.embGemma_embedder import GemmaTritonEmbedder, GemmaTritonEmbedderConfig

load_dotenv()

# --- Infrastructure Configuration ---
TRITON_URL = os.environ.get("TRITON_EMBEDDER_URL")
CHROMA_HOST = os.environ.get("CHROMA_DB_HOST")
CHROMA_PORT = int(os.environ.get("CHROMA_DB_PORT", 8000))
POSTGRES_CONFIG = get_postgres_config()

def load_agent_config(config_path: str) -> dict:
    """Loads the agent's YAML configuration file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.critical(f"FATAL: Configuration file not found at: {config_path}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"FATAL: Error loading YAML configuration: {e}")
        sys.exit(1)

def load_json_files(json_folder_path: str) -> list:
    """Loads all JSON files from a directory, skipping corrupted ones."""
    if not os.path.isdir(json_folder_path):
        logger.critical(f"FATAL: JSON folder not found at: {json_folder_path}")
        sys.exit(1)
        
    all_json_data = []
    file_list = [f for f in os.listdir(json_folder_path) if f.endswith('.json')]
    
    logger.info(f"Loading JSON files from '{json_folder_path}'...")
    for filename in tqdm(file_list, desc="Reading JSON files"):
        filepath = os.path.join(json_folder_path, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Basic validation to ensure the core key is present
                if 'passage_id' in data:
                    all_json_data.append(data)
                else:
                    logger.warning(f"Skipping {filename}: missing 'passage_id' key.")
        except json.JSONDecodeError:
            logger.error(f"SKIPPING: Could not parse JSON from {filename}. File is corrupt.")
        except Exception as e:
            logger.error(f"SKIPPING: Failed to read {filename} due to an unexpected error: {e}")
            
    logger.info(f"Successfully loaded and validated {len(all_json_data)} JSON files.")
    return all_json_data

def ingest_to_postgres(db_manager: SQLDatabaseManager, all_json_data: list):
    """Prepares and upserts structured data into PostgreSQL."""
    logger.info("--- Starting PostgreSQL Ingestion ---")
    
    postgres_records = []
    postgres_columns = ['passage_id', 'topic', 'text', 'date']

    for data in all_json_data:
        try:
            record = {key: data.get(key) for key in postgres_columns}
            if isinstance(record.get('date'), str):
                record['date'] = datetime.fromisoformat(record['date']).date()
            postgres_records.append(record)
        except (ValueError, TypeError) as e:
            logger.error(f"SKIPPING record for passage_id {data.get('passage_id')}: Invalid data format. Error: {e}")
            continue

    if not postgres_records:
        logger.warning("No valid records to insert into PostgreSQL. Skipping.")
        return

    update_columns = [col for col in postgres_columns if col != 'passage_id']
    
    try:
        logger.info(f"Upserting {len(postgres_records)} records into the 'passages' table...")
        db_manager.upsert_passages(insert_data=postgres_records, update_columns=update_columns)
        logger.success("✅ PostgreSQL ingestion complete.")
    except Exception as e:
        logger.critical(f"CRITICAL: A database error occurred during PostgreSQL upsert: {e}", exc_info=True)
        # In a real pipeline, this might trigger an alert. We exit to prevent partial states.
        sys.exit(1)

def ingest_to_chroma(chroma_client: chromadb.Client, embedder: GemmaTritonEmbedder, config: dict, all_json_data: list):
    """Prepares, embeds, and ingests data into multiple ChromaDB collections with robust error handling."""
    logger.info("--- Starting ChromaDB Ingestion ---")

    collection_key_map = {
        "PropositionsDB": "propositions", "SummariesDB": "summaries", "QuestionsDB": "question_patterns"
    }
    collections_to_process = config['vector_retriever']['collections']
    passage_id_meta_key = config['vector_retriever']['passage_id_meta_key']
    passage_embedding_function = embedder.as_chroma_passage_embedder()

    for collection_name in collections_to_process:
        json_key = collection_key_map.get(collection_name)
        if not json_key:
            logger.warning(f"No mapping found for collection '{collection_name}'. Skipping.")
            continue

        logger.info(f"\nProcessing collection: '{collection_name}'")
        try:
            chroma_client.delete_collection(name=collection_name)
            logger.info(f"Successfully deleted existing collection '{collection_name}'.")
        except Exception:
            logger.info(f"Collection '{collection_name}' does not exist. Creating a new one.")

        collection = chroma_client.get_or_create_collection(
            name=collection_name, embedding_function=passage_embedding_function
        )
        
        documents, metadatas, ids = [], [], []
        for data in all_json_data:
            passage_id = data['passage_id']
            doc_list = data.get(json_key, [])
            if not isinstance(doc_list, list):
                logger.warning(f"SKIPPING passage_id {passage_id} for collection '{collection_name}': '{json_key}' is not a list.")
                continue
            for i, doc_text in enumerate(doc_list):
                documents.append(str(doc_text))
                metadatas.append({passage_id_meta_key: passage_id})
                ids.append(f"{collection_name}_{passage_id}_{i}")

        if not documents:
            logger.warning(f"No valid documents found for collection '{collection_name}'. Skipping ingestion.")
            continue

        batch_size = 32  # Increased batch size for efficiency
        for i in tqdm(range(0, len(documents), batch_size), desc=f"Ingesting to {collection_name}"):
            try:
                collection.add(
                    documents=documents[i:i + batch_size],
                    metadatas=metadatas[i:i + batch_size],
                    ids=ids[i:i + batch_size]
                )
            except Exception as e:
                # Log the batch error but continue to the next batch.
                logger.error(f"Failed to ingest batch {i//batch_size} for '{collection_name}': {e}", exc_info=True)
        
        logger.success(f"✅ Finished ingestion for '{collection_name}'. Final count: {collection.count()} documents.")

def main():
    """Main function to orchestrate the entire ingestion pipeline."""
    parser = argparse.ArgumentParser(description="Ingest processed data into PostgreSQL and ChromaDB.")
    parser.add_argument("--config", type=str, required=True, help="Path to the agent's config.yaml file.")
    parser.add_argument("--json_folder", type=str, required=True, help="Path to the folder with processed JSON files.")
    args = parser.parse_args()

    embedder = None
    try:
        config = load_agent_config(args.config)
        all_json_data = load_json_files(args.json_folder)
        if not all_json_data:
            logger.error("No valid JSON data loaded. Exiting.")
            sys.exit(1)

        db_manager = SQLDatabaseManager(POSTGRES_CONFIG)
        embedder_config = GemmaTritonEmbedderConfig(triton_url=TRITON_URL)
        embedder = GemmaTritonEmbedder(config=embedder_config)
        chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        chroma_client.heartbeat() # Verify connection early

        ingest_to_postgres(db_manager, all_json_data)
        ingest_to_chroma(chroma_client, embedder, config, all_json_data)

    except Exception as e:
        logger.critical(f"A critical, unhandled error occurred during the ingestion process: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if embedder:
            embedder.close()
        logger.info("\n--- Data Ingestion Script Finished ---")

if __name__ == "__main__":
    main()

# --- END OF MODIFIED FILE: ingestion/ingest_data.py ---