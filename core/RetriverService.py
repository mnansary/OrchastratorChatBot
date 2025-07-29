# your_main_retriever_file.py

from langchain_community.vectorstores import Chroma
import warnings
import os
from typing import Dict, Any, List
from dotenv import load_dotenv
# Import your JinaV3Embeddings class from its file
from .embedding import JinaV3TritonEmbeddings
warnings.filterwarnings("ignore")
load_dotenv()


class RetrieverService:
    def __init__(self):
        """
        Initializes a more powerful, flexible retriever service.
        """
        print("Initializing Advanced RetrieverService...")
        self.embedding_model = JinaV3TritonEmbeddings()
        vector_db_path = os.getenv("VECTOR_DB_PATH")
        self.vectorstore = Chroma(
            persist_directory=vector_db_path,
            embedding_function=self.embedding_model
        )
        
        try:
            db_count = self.vectorstore._collection.count()
            print(f"✅ Advanced RetrieverService initialized successfully. Vector store at '{vector_db_path}' contains {db_count} documents.")
        except Exception as e:
            print(f"⚠️ Warning: Could not get count from vector store: {e}")

    def retrieve(self, query: str, k: int = 3, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Retrieves relevant passages with dynamic k and metadata filtering.

        Args:
            query (str): The user's question.
            k (int): The number of documents to retrieve for this specific query.
            filters (dict, optional): A dictionary for metadata filtering. 
                                      Example: {"category": "Beef items and products"}

        Returns:
            dict: A dictionary containing the query and a list of retrieved passages.
        """
        print(f"\nPerforming advanced retrieval for query: \"{query}\" with k={k} and filters={filters}")
        
        # Use similarity_search_with_score with dynamic k and the 'filter' argument
        # THIS IS THE CORRECTED LINE:
        docs_with_scores = self.vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter=filters  # The correct keyword for the LangChain wrapper is 'filter'
        )

        retrieved_passages = []
        if not docs_with_scores:
            print("No relevant documents found with the given criteria.")
        else:
            for doc, score in docs_with_scores:
                retrieved_passages.append({
                    "text": doc.page_content,
                    "url": doc.metadata.get("url", "URL not found"),
                    "score": score,
                    "metadata": doc.metadata
                })
            print(f"Found {len(retrieved_passages)} relevant passages.")
            
        retrieved_passages.sort(key=lambda x: x["score"])

        return {
            "query": query,
            "retrieved_passages": retrieved_passages
        }

# --- Example Usage (Unchanged) ---
if __name__ == "__main__":
    import json

    # 1. Initialize the service
    retriever_service = RetrieverService()
    
    # --- Example 1: A simple search using default k=3 ---
    print("\n\n--- Example 1: Simple Search (default k=3) ---")
    results_1 = retriever_service.retrieve(query="What is your refund policy?")
    print(json.dumps(results_1, indent=2, ensure_ascii=False))

    # --- Example 2: A search with a custom k value ---
    print("\n\n--- Example 2: Custom 'k' Search (k=5) ---")
    results_2 = retriever_service.retrieve(
        query="all beef products", 
        k=5
    )
    print(json.dumps(results_2, indent=2, ensure_ascii=False))

    # --- Example 3: A search using a metadata filter ---
    print("\n\n--- Example 3: Metadata Filter Search ---")
    results_3 = retriever_service.retrieve(
        query="sausages", 
        k=3,
        filters={"topic": "Sausages items and products"}
    )
    print(json.dumps(results_3, indent=2, ensure_ascii=False))

    # --- Example 4: A combined search with both filter and custom k ---
    print("\n\n--- Example 4: Combined Filter and Custom 'k' Search ---")
    results_4 = retriever_service.retrieve(
        query="chicken snacks",
        k=2,
        filters={"topic": "Snacks items and products"}
    )
    print(json.dumps(results_4, indent=2, ensure_ascii=False))