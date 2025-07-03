import json
import sys
from typing import Dict, Any, Deque, Tuple, Generator

# Use standard library deque for efficient history management
from collections import deque

# Import all our custom components
from core.RetriverService import RetrieverService
from core.LLMservice import LLMService
from core.prompts import ANALYST_PROMPT, STRATEGIST_PROMPTS
from core.config import VECTOR_DB_PATH, MODEL_URL

class ProactiveChatService:
    def __init__(self, history_length: int = 10):
        # NOTE: num_passages_to_retrieve is removed from here.
        print("Initializing ProactiveChatService...")
        self.retriever = RetrieverService(vector_db_path=VECTOR_DB_PATH) # Simplified init
        self.llm_service = LLMService(base_url=MODEL_URL)
        self.history: Deque[Tuple[str, str]] = deque(maxlen=history_length)
        print(f"✅ ProactiveChatService initialized successfully. History window: {history_length} turns.")

    def _format_history(self) -> str:
        """Formats the conversation history into a readable string for prompts."""
        if not self.history:
            return "No conversation history yet."
        return "\n".join([f"User: {user_q}\nAI: {ai_a}" for user_q, ai_a in self.history])

    def _run_analyst_stage(self, user_input: str, history_str: str) -> Dict[str, Any] | None:
        """Executes the Analyst stage: gets a structured JSON plan from the LLM."""
        print("\n----- 🕵️ Analyst Stage -----")
        prompt = ANALYST_PROMPT.format(history=history_str, question=user_input)
        try:
            response_text = self.llm_service.invoke(prompt, temperature=0.1, max_tokens=512)
            plan = json.loads(response_text)
            print("✅ Analyst plan generated successfully:")
            print(json.dumps(plan, indent=2))
            return plan
        except (json.JSONDecodeError, Exception) as e:
            print(f"❌ CRITICAL: Analyst stage failed: {e}")
            return None
            
    def _run_retriever_stage(self, plan: Dict[str, Any]) -> Tuple[str, list]:
        """Executes the Retriever stage based on the Analyst's detailed plan."""
        print("\n----- 📚 Retriever Stage -----")
        
        query = plan.get("query_for_retriever", "")
        k = plan.get("k_for_retriever", 0)
        filters = plan.get("metadata_filter", None)

        if k == 0 or not query:
            print("Skipping retrieval as per Analyst's plan.")
            return "No retrieval was performed.", []

        print(f"🔍 Querying retriever with: '{query}', k={k}, filters={filters}")
        retrieval_results = self.retriever.retrieve(query, k=k, filters=filters)
        retrieved_passages = retrieval_results.get("retrieved_passages", [])

        if not retrieved_passages:
            print("⚠️ Retriever found no documents.")
            return "No information found matching the criteria.", []
        
        combined_context = "\n\n---\n\n".join([doc["text"] for doc in retrieved_passages])
        print(f"✅ Retriever found {len(retrieved_passages)} documents.")
        return combined_context, retrieved_passages

    def _run_strategist_stage(self, plan: Dict[str, Any], context: str, user_input: str, history_str: str) -> Generator[str, None, None]:
        """Executes the Strategist stage: returns a generator that streams the final response."""
        print("\n----- 🎭 Strategist Stage -----")
        strategy = plan.get("response_strategy", "RESPOND_WARMLY")
        print(f"✍️ Executing strategy: '{strategy}'")

        prompt_template = STRATEGIST_PROMPTS.get(strategy)
        if not prompt_template:
            print(f"❌ WARNING: Invalid strategy '{strategy}'. Defaulting.")
            prompt_template = STRATEGIST_PROMPTS["RESPOND_WARMLY"]

        prompt = prompt_template.format(
            context=context,
            question=user_input,
            history=history_str
        )
        
        return self.llm_service.stream(
            prompt,
            temperature=0.7,
            max_tokens=4000,
            top_p=0.9,
            repetition_penalty=1.05
        )

    def chat(self, user_input: str) -> Generator[Dict[str, Any], None, None]:
        """Main entry point, orchestrating the new, more robust pipeline."""
        print(f"\n==================== NEW CHAT TURN: User said '{user_input}' ====================")
        history_str = self._format_history()

        plan = self._run_analyst_stage(user_input, history_str)
        if not plan:
            yield {"type": "error", "content": "I'm sorry, I'm having a little trouble. Could you rephrase?"}
            return

        combined_context, retrieved_passages = self._run_retriever_stage(plan)
        
        answer_generator = self._run_strategist_stage(plan, combined_context, user_input, history_str)
        
        full_answer_list = []
        for chunk in answer_generator:
            full_answer_list.append(chunk)
            yield {
                "type": "answer_chunk",
                "content": chunk
            }
        
        final_answer = "".join(full_answer_list).strip()

        self.history.append((user_input, final_answer))
        # sources = list(set([doc.get("url") for doc in retrieved_passages if doc.get("url")]))
        
        # yield {
        #     "type": "final_data",
        #     "content": {"sources": sources}
        # }
        print("\n-------------------- STREAM COMPLETE --------------------")

# --- Example Usage: Simulating a Conversation to Test the Pipeline ---
if __name__ == "__main__":
    # 1. Initialize the service
    # Using a shorter history for testing so we can see it being managed.
    chat_service = ProactiveChatService(history_length=5)
    
    # 2. Define a list of test cases to simulate a conversation
    test_conversation = [
        "Hello!",
        "Do you sell fish?",
        "What about your beef sausages? Are they spicy?",
        "Great, can you add two packs to my cart?",
        "Okay, I'll do that myself. By the way, who founded Bengal Meat?",
        "I see. One last thing, my delivery is late.",
        "Thanks for the help!"
    ]
    
    # 3. Loop through the conversation and process each turn
    for turn in test_conversation:
        print(f"\n\n\n>>>>>>>>>>>>>>>>>> User Input: {turn} <<<<<<<<<<<<<<<<<<")
        print("\n<<<<<<<<<<<<<<<<<< Bot Response >>>>>>>>>>>>>>>>>>")
        
        final_sources = []
        try:
            # The client code iterates through the generator yielded by chat()
            for event in chat_service.chat(turn):
                if event["type"] == "answer_chunk":
                    # Print each chunk as it arrives to simulate a streaming UI
                    print(event["content"], end="", flush=True)
                elif event["type"] == "final_data":
                    # Store the final metadata for display after the stream
                    final_sources = event["content"]["sources"]
                elif event["type"] == "error":
                    print(event["content"], end="", flush=True)

            # After the stream is complete, print the sources if any were found
            if final_sources:
                print(f"\n[Sources Found: {', '.join(final_sources)}]")
            print("\n<<<<<<<<<<<<<<<<<< End of Response >>>>>>>>>>>>>>>>>>")

        except Exception as e:
            print(f"\nAn unexpected error occurred during the test run: {e}")