# core/LLMservice.py

import requests
import json
import base64
import os
from dotenv import load_dotenv
from typing import Generator, Any

class LLMService:
    """
    A self-configuring service class to interact with a vLLM-powered OpenAI-compatible API.
    It automatically loads its configuration (API key, URL, model name) from a .env file.
    """
    def __init__(self):
        """
        Initializes the LLMService by loading configuration from environment variables.
        
        Raises:
            ValueError: If any of the required environment variables 
                        (LLM_MODEL_BASE_URL, LLM_MODEL_API_KEY, LLM_MODEL_NAME) are not set.
        """
        load_dotenv() # Load variables from .env file into the environment
        
        self.base_url = os.getenv("LLM_MODEL_BASE_URL")
        self.api_key = os.getenv("LLM_MODEL_API_KEY")
        self.model = os.getenv("LLM_MODEL_NAME")

        if not all([self.base_url, self.api_key, self.model]):
            raise ValueError(
                "❌ Configuration Error: One or more required environment variables are missing.\n"
                "Please ensure your .env file contains:\n"
                "- LLM_MODEL_BASE_URL\n"
                "- LLM_MODEL_API_KEY\n"
                "- LLM_MODEL_NAME"
            )

        self.base_url = self.base_url.rstrip('/')
        self.chat_url = f"{self.base_url}/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        print(f"✅ LLMService initialized for model '{self.model}' at endpoint: {self.chat_url}")

    def _process_stream(self, response: requests.Response) -> Generator[str, None, None]:
        """
        Processes a streaming HTTP response and yields decoded content chunks.
        (This method remains unchanged)
        """
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    content = decoded_line[len('data: '):]
                    if content.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(content)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        text_chunk = delta.get("content")
                        if text_chunk:
                            yield text_chunk
                    except json.JSONDecodeError:
                        print(f"\n[Warning] Could not decode JSON chunk: {content}")

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """
        Sends a request for a single, complete response (non-streaming).
        (This method remains unchanged)
        """
        messages = [{"role": "user", "content": prompt}]
        payload = {"model": self.model, "messages": messages, "stream": False, **kwargs}
        
        try:
            response = requests.post(self.chat_url, headers=self.headers, json=payload, timeout=120)
            response.raise_for_status()
            
            response_data = response.json()
            
            if "choices" in response_data and response_data["choices"]:
                message = response_data["choices"][0].get("message", {})
                content = message.get("content", "")
                return content.strip()
            else:
                print("❌ ERROR: LLM response is missing 'choices' array or it is empty.")
                return ""

        except requests.exceptions.HTTPError as e:
            print(f"\n[Error] HTTP Error during invoke: {e}\nResponse Body: {e.response.text}")
            return ""
        except requests.exceptions.RequestException as e:
            print(f"\n[Error] Network error during invoke: {e}")
            return ""
        except json.JSONDecodeError:
            print(f"\n[Error] Failed to decode JSON from LLM response. Response text: '{response.text}'")
            return ""

    def stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """
        Connects to the streaming endpoint and yields text chunks as they arrive.
        (This method remains unchanged)
        """
        messages = [{"role": "user", "content": prompt}]
        payload = {"model": self.model, "messages": messages, "stream": True, **kwargs}
        
        try:
            response = requests.post(self.chat_url, headers=self.headers, json=payload, timeout=120, stream=True)
            response.raise_for_status()
            yield from self._process_stream(response)
        except requests.exceptions.RequestException as e:
            print(f"\n[Error] An error occurred during stream: {e}")
            raise

    def image_stream(self, prompt: str, image_path: str, **kwargs: Any) -> Generator[str, None, None]:
        """
        Sends an image and a text prompt for a streaming multi-modal response.
        (This method remains unchanged)
        """
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            print(f"\n[Error] Image file not found at: {image_path}")
            return

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
            ]
        }]
        payload = {"model": self.model, "messages": messages, "stream": True, **kwargs}

        try:
            response = requests.post(self.chat_url, headers=self.headers, json=payload, timeout=180, stream=True)
            response.raise_for_status()
            yield from self._process_stream(response)
        except requests.exceptions.RequestException as e:
            print(f"\n[Error] An error occurred during image stream: {e}")
            raise

# This block demonstrates how to use the self-configuring LLMService class.
# It assumes you have a .env file in the same directory with the required variables.
if __name__ == "__main__":
    
    try:
        # --- Initialize the service ---
        # No parameters needed; it configures itself from the .env file.
        llm_service = LLMService()

        # --- Example 1: Non-streaming text generation using invoke() ---
        print("\n" + "="*20 + " EXAMPLE 1: INVOKE " + "="*20)
        prompt_invoke = "Explain what an API gateway is in simple terms."
        print(f"👤 User Prompt: {prompt_invoke}")
        print("🤖 AI Response (Invoke):")
        response_invoke = llm_service.invoke(prompt_invoke, max_tokens=150)
        print(response_invoke)
        print("="*55)

        # --- Example 2: Streaming text generation using stream() ---
        print("\n" + "="*20 + " EXAMPLE 2: STREAM " + "="*20)
        prompt_stream = "List three benefits of using Docker for application deployment."
        print(f"👤 User Prompt: {prompt_stream}")
        print("🤖 AI Response (Stream):")
        full_response_stream = ""
        try:
            for chunk in llm_service.stream(prompt_stream, max_tokens=150):
                print(chunk, end="", flush=True)
                full_response_stream += chunk
            print() # for a new line after the stream finishes
        except Exception as e:
            print(f"An error occurred during the streaming example: {e}")
        print("="*55)

    except ValueError as e:
        # This will catch the error from __init__ if the .env file is misconfigured
        print(e)