import os
import sys
from typing import Dict, Any, Deque, Tuple, Generator
from collections import deque
from dotenv import load_dotenv

# Ensure the 'core' directory is in the Python path
# This might be needed if you run the script from the root directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))

# --- Import all our custom components ---
# Assumes RetrieverService is in a 'core' subdirectory
from core.RetriverService import RetrieverService 
# Assumes your modernized LLMService is in a 'core' subdirectory
from core.LLMservice import LLMService, ContextLengthExceededError 
# Import the new, centralized prompts and Pydantic model from a 'core' subdirectory
from core.prompts import ANALYST_PROMPT, STRATEGIST_PROMPTS, AnalystPlan

load_dotenv()

class ProactiveChatService:
    def __init__(self, history_length: int = 10):
        """Initializes the chat service, loading all necessary components."""
        print("Initializing ProactiveChatService...")
        self.retriever = RetrieverService()
        self.llm_service = LLMService()
        self.history: Deque[Tuple[str, str]] = deque(maxlen=history_length)
        print(f"✅ ProactiveChatService initialized successfully. History window: {history_length} turns.")

    def _format_history(self) -> str:
        """Formats the conversation history into a readable string for the LLM."""
        if not self.history:
            return "No conversation history yet."
        return "\n".join([f"User: {user_q}\nAI: {ai_a}" for user_q, ai_a in self.history])

    def _run_analyst_stage(self, user_input: str, history_str: str) -> AnalystPlan | None:
        """
        Executes the Analyst stage using a structured output call to get a validated plan.
        """
        print("\n----- 🕵️ Analyst Stage (Structured) -----")
        prompt = ANALYST_PROMPT.format(history=history_str, question=user_input)
        try:
            # Use the structured output method from the LLM service for reliability
            plan = self.llm_service.invoke_structured(
                prompt, 
                response_model=AnalystPlan, 
                temperature=0.0
            )
            print("✅ Analyst plan parsed successfully via Pydantic:")
            # .model_dump_json is a Pydantic method for clean printing
            print(plan.model_dump_json(indent=2))
            return plan
        except (ValueError, ContextLengthExceededError) as e:
            print(f"❌ CRITICAL: Analyst stage failed: {e}")
            return None
        except Exception as e:
            print(f"❌ CRITICAL: An unexpected error occurred in the Analyst stage: {e}")
            return None
    
    def _run_retriever_stage(self, plan: AnalystPlan) -> Tuple[str, list]:
        """
        Executes the Retriever stage based on the simplified Analyst plan.
        Uses a fixed K value of 3 and no metadata filters.
        """
        print("\n----- 📚 Retriever Stage -----")
        
        query = plan.query_for_retriever
        K_VALUE = 3 # Hardcoded K value as per requirements

        if not query:
            print("Skipping retrieval as per Analyst's plan (empty query).")
            return "No retrieval was performed.", []

        print(f"🔍 Querying retriever with: '{query}', k={K_VALUE}")
        # Filters are set to None as they are not part of the plan
        retrieval_results = self.retriever.retrieve(query, k=K_VALUE, filters=None)
        retrieved_passages = retrieval_results.get("retrieved_passages", [])

        if not retrieved_passages:
            print("⚠️ Retriever found no documents.")
            return "No information found matching your query.", []
        
        combined_context = "\n\n---\n\n".join([doc["text"] for doc in retrieved_passages])
        print(f"✅ Retriever found {len(retrieved_passages)} documents.")
        return combined_context, retrieved_passages

    def _run_strategist_stage(self, plan: AnalystPlan, context: str, user_input: str, history_str: str) -> Generator[str, None, None]:
        """
        Executes the Strategist stage, selecting the correct prompt and streaming the response.
        """
        print("\n----- 🎭 Strategist Stage -----")
        strategy = plan.response_strategy
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
            max_tokens=2048
        )

    def chat(self, user_input: str) -> Generator[Dict[str, Any], None, None]:
        """
        Main entry point for a chat turn, orchestrating the pipeline.
        """
        print(f"\n==================== NEW CHAT TURN: User said '{user_input}' ====================")
        history_str = self._format_history()

        # 1. Analyst Stage
        plan = self._run_analyst_stage(user_input, history_str)
        if not plan:
            yield {"type": "error", "content": "I'm sorry, I'm having a little trouble thinking. Could you please rephrase?"}
            return

        # 2. Retriever Stage
        combined_context, retrieved_passages = self._run_retriever_stage(plan)
        
        # 3. Strategist Stage
        answer_generator = self._run_strategist_stage(plan, combined_context, user_input, history_str)
        
        # Stream the final answer and update history
        full_answer_list = []
        for chunk in answer_generator:
            full_answer_list.append(chunk)
            yield {
                "type": "answer_chunk",
                "content": chunk
            }
        
        final_answer = "".join(full_answer_list).strip()
        self.history.append((user_input, final_answer))
        
        print("\n-------------------- STREAM COMPLETE --------------------")


if __name__ == "__main__":
    try:
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
            
            try:
                for event in chat_service.chat(turn):
                    if event["type"] == "answer_chunk":
                        print(event["content"], end="", flush=True)
                    elif event["type"] == "error":
                        print(event["content"], end="", flush=True)

                print("\n<<<<<<<<<<<<<<<<<< End of Response >>>>>>>>>>>>>>>>>>")

            except Exception as e:
                print(f"\nAn unexpected error occurred during the test run for this turn: {e}")
                
    except Exception as e:
        print(f"\n❌ A critical error occurred during initialization: {e}")