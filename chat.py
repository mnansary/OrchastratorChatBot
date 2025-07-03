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
    def __init__(
        self,
        num_passages_to_retrieve: int = 3,
        history_length: int = 10
    ):
        """
        Initializes the proactive, multi-stage chat service.
        """
        print("Initializing ProactiveChatService...")
        self.retriever = RetrieverService(
            vector_db_path=VECTOR_DB_PATH,
            num_passages_to_retrieve=num_passages_to_retrieve
        )
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

    def _run_retriever_stage(self, query: str) -> Tuple[str, list]:
        """Executes the Retriever stage: fetches and combines factual documents."""
        print("\n----- 📚 Retriever Stage -----")
        print(f"🔍 Querying retriever with: '{query}'")
        retrieval_results = self.retriever.retrieve(query)
        retrieved_passages = retrieval_results.get("retrieved_passages", [])
        if not retrieved_passages:
            print("⚠️ Retriever found no documents.")
            return "No information found.", []
        combined_context = "\n\n---\n\n".join([doc["text"] for doc in retrieved_passages])
        print(f"✅ Retriever found {len(retrieved_passages)} documents.")
        return combined_context, retrieved_passages

    # *** CHANGED: This method now returns a generator ***
    def _run_strategist_stage(self, plan: Dict[str, Any], context: str, user_input: str, history_str: str) -> Generator[str, None, None]:
        """
        Executes the Strategist stage: returns a generator that streams the final response.
        """
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
        
        # *** CHANGED: Use the .stream() method instead of .invoke() ***
        return self.llm_service.stream(
            prompt,
            temperature=0.7,
            max_tokens=4000,
            top_p=0.9,
            repetition_penalty=1.05
        )

    # *** CHANGED: The main `chat` method is now a generator ***
    def chat(self, user_input: str) -> Generator[Dict[str, Any], None, None]:
        """
        Main entry point for the chat service. It now yields a stream of events.
        Possible event types: 'error', 'answer_chunk', 'final_data'.
        """
        print(f"\n==================== NEW CHAT TURN: User said '{user_input}' ====================")
        history_str = self._format_history()

        # STAGE 1: ANALYZE AND PLAN
        plan = self._run_analyst_stage(user_input, history_str)
        if not plan:
            yield {
                "type": "error",
                "content": "I'm sorry, I'm having a little trouble understanding. Could you please rephrase?"
            }
            return

        # STAGE 2: RETRIEVE INFORMATION
        query_for_retriever = plan.get("query_for_retriever", user_input)
        combined_context, retrieved_passages = self._run_retriever_stage(query_for_retriever)
        
        # STAGE 3: STREAM STRATEGIC RESPONSE
        answer_generator = self._run_strategist_stage(plan, combined_context, user_input, history_str)
        
        # *** NEW: Accumulate the full answer while streaming for history ***
        full_answer_list = []
        for chunk in answer_generator:
            full_answer_list.append(chunk)
            yield {
                "type": "answer_chunk",
                "content": chunk
            }
        
        # Join the chunks to get the final complete answer
        final_answer = "".join(full_answer_list).strip()

        # STAGE 4: UPDATE STATE AND YIELD FINAL METADATA
        self.history.append((user_input, final_answer))
        
        sources = list(set([doc["url"] for doc in retrieved_passages if doc.get("url")]))
        
        yield {
            "type": "final_data",
            "content": {"sources": sources}
        }
        print("\n-------------------- STREAM COMPLETE --------------------")


# --- Example Usage: How to consume the streaming service ---
if __name__ == "__main__":
    chat_service = ProactiveChatService(num_passages_to_retrieve=2, history_length=5)
    
    conversation = [
        "Hello there!",
        "What kind of beef products do you sell?",
        "What's the price of the ribeye steak?",
        "Okay thanks. By the way, my last order seems to be delayed."
    ]
    
    for turn in conversation:
        print(f"\n> User: {turn}")
        print("> Bengal Meat:", end=" ")
        
        # *** CHANGED: The client now loops through the generator from chat() ***
        final_sources = []
        try:
            for event in chat_service.chat(turn):
                if event["type"] == "answer_chunk":
                    # Print each chunk as it arrives to simulate streaming UI
                    print(event["content"], end="", flush=True)
                elif event["type"] == "final_data":
                    # Store the final metadata
                    final_sources = event["content"]["sources"]
                elif event["type"] == "error":
                    print(event["content"])

            # After the stream is complete, print the sources
            if final_sources:
                print(f"\n[Sources: {', '.join(final_sources)}]")
            print("\n") # Newline for clean separation

        except Exception as e:
            print(f"\nAn error occurred during chat processing: {e}")