# llm_service.py

import os
import logging
from dotenv import load_dotenv
from openai import OpenAI, BadRequestError
from pydantic import BaseModel, ValidationError, Field
from typing import Generator, Any, Type, TypeVar, List

# --- Setup ---
# Load environment variables from a .env file
load_dotenv()
# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Custom Exceptions for Clarity ---
class LLMConfigError(Exception):
    """Custom exception for configuration problems."""
    pass

class ContextLengthExceededError(Exception):
    """Custom exception for when a prompt exceeds the model's context window."""
    pass

# Generic type variable for Pydantic models for clean type hinting.
PydanticModel = TypeVar("PydanticModel", bound=BaseModel)


class LLMService:
    """
    A synchronous client for OpenAI-compatible APIs using the 'openai' library.
    It self-configures from your specific environment variables.
    """
    def __init__(self):
        """
        Initializes the service using environment variables:
        - LLM_MODEL_BASE_URL
        - LLM_MODEL_API_KEY
        - LLM_MODEL_NAME
        - LLM_MAX_CONTEXT_TOKENS
        """
        base_url = os.getenv("LLM_MODEL_BASE_URL")
        api_key = os.getenv("LLM_MODEL_API_KEY")
        self.model = os.getenv("LLM_MODEL_NAME")
        max_tokens_str = os.getenv("LLM_MAX_CONTEXT_TOKENS")

        if not all([base_url, api_key, self.model, max_tokens_str]):
            raise LLMConfigError(
                "One or more required environment variables are missing. "
                "Ensure LLM_MODEL_BASE_URL, LLM_MODEL_API_KEY, LLM_MODEL_NAME, "
                "and LLM_MAX_CONTEXT_TOKENS are set in your .env file."
            )

        self.max_context_tokens = int(max_tokens_str)
        
        # Initialize the OpenAI client with the loaded configuration
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        
        logging.info(f"✅ LLMService initialized for model '{self.model}' at URL '{base_url}'.")

    def _handle_bad_request(self, e: BadRequestError):
        """Helper to raise a custom exception for context length errors."""
        if "context length" in str(e).lower() or "too large" in str(e).lower():
            logging.error(f"Prompt exceeded context window for model {self.model}.")
            raise ContextLengthExceededError(f"Prompt is too long for the model's {self.max_context_tokens} token limit.") from e
        else:
            logging.error(f"Unhandled BadRequestError: {e}")
            raise

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """Sends a request for a single, complete response (non-streaming)."""
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, **kwargs)
            return response.choices[0].message.content or ""
        except BadRequestError as e:
            self._handle_bad_request(e)
            raise
        except Exception as e:
            logging.error(f"An error occurred during invoke: {e}", exc_info=True)
            raise

    def stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """Connects to the streaming endpoint and yields text chunks."""
        messages = [{"role": "user", "content": prompt}]
        try:
            stream = self.client.chat.completions.create(model=self.model, messages=messages, stream=True, **kwargs)
            for chunk in stream:
                content_chunk = chunk.choices[0].delta.content
                if content_chunk:
                    yield content_chunk
        except BadRequestError as e:
            self._handle_bad_request(e)
            raise
        except Exception as e:
            logging.error(f"An error occurred during stream: {e}", exc_info=True)
            raise

    def invoke_structured(
        self, prompt: str, response_model: Type[PydanticModel], **kwargs: Any
    ) -> PydanticModel:
        """
        Invokes the model and parses the response into a Pydantic object.
        Uses the model's native JSON mode for reliable output.
        """
        structured_prompt = (
            f"{prompt}\n\n"
            "Your response MUST be a single, valid JSON object that conforms to the following schema. "
            "Do not include any other text, explanations, or markdown formatting.\n"
            f"JSON Schema: {response_model.model_json_schema()}"
        )
        messages = [{"role": "user", "content": structured_prompt}]

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, response_format={"type": "json_object"}, **kwargs
            )
            json_response_str = response.choices[0].message.content
            if not json_response_str:
                raise ValueError("The model returned an empty JSON response.")
            
            return response_model.model_validate_json(json_response_str)
            
        except BadRequestError as e:
            self._handle_bad_request(e)
            raise
        except ValidationError as e:
            logging.error(f"Pydantic validation failed for model response. Error: {e}")
            logging.error(f"Raw model output was: {json_response_str}")
            raise
        except Exception as e:
            logging.error(f"An error occurred during structured invoke: {e}", exc_info=True)
            raise


# ======================================================================================
#   TESTING BLOCK: Run this file directly to test the LLMService
# ======================================================================================
if __name__ == "__main__":
    
    # Define a simple Pydantic model for the structured output test
    class AnalysisResult(BaseModel):
        summary: str = Field(description="A brief summary of the text.")
        keywords: List[str] = Field(description="A list of 3-5 main keywords.")

    try:
        # 1. Initialize the service (it will read from your .env file)
        llm_service = LLMService()

        # ==================== EXAMPLE 1: invoke() ====================
        print("\n" + "="*20 + " EXAMPLE 1: INVOKE (Non-streaming) " + "="*20)
        invoke_prompt = "Explain the concept of a Large Language Model in one sentence."
        print(f"👤 User Prompt: {invoke_prompt}")
        response = llm_service.invoke(invoke_prompt, temperature=0.5, max_tokens=100)
        print(f"🤖 AI Response:\n{response}")
        print("="*65)
        
        # ==================== EXAMPLE 2: stream() ====================
        print("\n" + "="*20 + " EXAMPLE 2: STREAM " + "="*20)
        stream_prompt = "List three benefits of using Python for data science."
        print(f"👤 User Prompt: {stream_prompt}")
        print("🤖 AI Response (streaming):")
        full_response = ""
        for chunk in llm_service.stream(stream_prompt, temperature=0.7, max_tokens=150):
            print(chunk, end="", flush=True)
            full_response += chunk
        print("\n" + "="*54)

        # ==================== EXAMPLE 3: invoke_structured() ====================
        print("\n" + "="*20 + " EXAMPLE 3: INVOKE_STRUCTURED (JSON) " + "="*20)
        structured_prompt = "Analyze the following text: 'The sun is a star at the center of the Solar System. It is a nearly perfect ball of hot plasma, heated to incandescence by nuclear fusion reactions in its core.'"
        print(f"👤 User Prompt: {structured_prompt}")
        try:
            structured_response = llm_service.invoke_structured(
                structured_prompt, 
                AnalysisResult, 
                temperature=0.1
            )
            print("🤖 AI Response (Pydantic Object):")
            print(structured_response)
            print(f"\nType of response: {type(structured_response)}")
            print(f"Accessing data: structured_response.summary = '{structured_response.summary}'")
        except Exception as e:
            print(f"❌ Structured call failed: {e}")
        print("="*68)

    except LLMConfigError as e:
        print(f"❌ CONFIGURATION ERROR: {e}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred during the test: {e}")