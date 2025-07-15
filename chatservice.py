import os
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
from dotenv import load_dotenv
load_dotenv()

class ProactiveChatService:
    def __init__(self, history_length: int = 100):
        print("Initializing ProactiveChatService...")
        self.retriever = RetrieverService(vector_db_path=VECTOR_DB_PATH)
        
        base_url = os.getenv("LLM_MODEL_BASE_URL")
        api_key = os.getenv("LLM_MODEL_API_KEY")
        model_name = os.getenv("LLM_MODEL_NAME")

        if not all([base_url, api_key, model_name]):
            raise ValueError("LLM configuration (BASE_URL, API_KEY, MODEL_NAME) not found in .env file.")

        self.llm_service = LLMService(base_url=base_url, api_key=api_key, model=model_name)
        self.history: Deque[Tuple[str, str]] = deque(maxlen=history_length)
        print(f"✅ ProactiveChatService initialized successfully. History window: {history_length} turns.")

    def _format_history(self) -> str:
        if not self.history:
            return "No conversation history yet."
        return "\n".join([f"User: {user_q}\nAI: {ai_a}" for user_q, ai_a in self.history])

    # ===================================================================================
    #   THIS IS THE CORRECTED FUNCTION
    # ===================================================================================
    def _run_analyst_stage(self, user_input: str, history_str: str) -> Dict[str, Any] | None:
        """Executes the Analyst stage: gets a structured JSON plan from the LLM."""
        print("\n----- 🕵️ Analyst Stage -----")
        prompt = ANALYST_PROMPT.format(history=history_str, question=user_input)
        response_text = ""
        try:
            response_text = self.llm_service.invoke(prompt, temperature=0.1, max_tokens=2048)

            # --- START: NEW SANITIZATION LOGIC ---
            # Find the first '{' and the last '}' to extract the JSON object
            json_start_index = response_text.find('{')
            json_end_index = response_text.rfind('}')

            if json_start_index != -1 and json_end_index != -1:
                clean_json_str = response_text[json_start_index : json_end_index + 1]
                # Now, try to parse the cleaned string
                plan = json.loads(clean_json_str)
                print("✅ Analyst plan parsed successfully after cleaning:")
                print(json.dumps(plan, indent=2))
                return plan
            else:
                # If we can't find a JSON object, we fail gracefully
                print("❌ CRITICAL: Could not find a valid JSON object in the LLM's response.")
                print(f"LLM Response was: '{response_text}'")
                return None
            # --- END: NEW SANITIZATION LOGIC ---

        except (json.JSONDecodeError, Exception) as e:
            print(f"❌ CRITICAL: Analyst stage failed even after cleaning: {e}")
            print(f"Original LLM Response was: '{response_text}'")
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
            print(f"❌ WARNING: Invalid strategy '{strategy}'. Defaulting to RESPOND_WARMLY.")
            prompt_template = STRATEGIST_PROMPTS["RESPOND_WARMLY"]

        prompt = prompt_template.format(
            context=context,
            question=user_input,
            history=history_str
        )
        
        return self.llm_service.stream(
            prompt,
            temperature=0.7,
            max_tokens=4096,
            top_p=0.9,
            repetition_penalty=1.05
        )

    def chat(self, user_input: str) -> Generator[Dict[str, Any], None, None]:
        """Main entry point, orchestrating the pipeline and yielding structured events."""
        print(f"\n==================== NEW CHAT TURN: User said '{user_input}' ====================")
        history_str = self._format_history()

        plan = self._run_analyst_stage(user_input, history_str)
        if not plan:
            yield {"type": "error", "content": "I'm sorry, I'm having a little trouble thinking. Could you please rephrase?"}
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
        
        # sources = list(set([doc["metadata"].get("url", "N/A") for doc in retrieved_passages if doc.get("metadata")]))
        
        # yield {
        #     "type": "final_data",
        #     "content": {"sources": sources}
        # }
        print("\n-------------------- STREAM COMPLETE --------------------")


if __name__ == "__main__":
    chat_service = ProactiveChatService(history_length=5)
    
    test_conversation = [
        "Hello!",
        "Do you sell fish?",
        "What about your beef sausages? Are they spicy?",
        "Great, can you add two packs to my cart?",
        "Okay, I'll do that myself. By the way, who founded Bengal Meat?",
        "I see. One last thing, my delivery is late.",
        "Thanks for the help!"
    ]
    
    for turn in test_conversation:
        print(f"\n\n\n>>>>>>>>>>>>>>>>>> User Input: {turn} <<<<<<<<<<<<<<<<<<")
        print("\n<<<<<<<<<<<<<<<<<< Bot Response >>>>>>>>>>>>>>>>>>")
        
        final_sources = []
        try:
            for event in chat_service.chat(turn):
                if event["type"] == "answer_chunk":
                    print(event["content"], end="", flush=True)
                elif event["type"] == "final_data":
                    final_sources = event["content"]["sources"]
                elif event["type"] == "error":
                    print(event["content"], end="", flush=True)

            if final_sources:
                print(f"\n\n[Sources Found: {', '.join(final_sources)}]")
            print("\n<<<<<<<<<<<<<<<<<< End of Response >>>>>>>>>>>>>>>>>>")

        except Exception as e:
            print(f"\nAn unexpected error occurred during the test run: {e}")