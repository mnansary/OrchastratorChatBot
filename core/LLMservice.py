import requests
import json
from typing import Generator, Dict, Any

class LLMService:
    """
    A simple, synchronous client for a custom LLM web service.
    
    This class uses the 'requests' library for all communication, providing
    a straightforward interface for both invoke and stream operations.
    """

    def __init__(self, base_url: str = "http://localhost:24434"):
        """
        Initializes the client for the LLM service.

        Args:
            base_url (str): The base URL of the LLM service (e.g., http://localhost:24434).
        """
        self.base_url = base_url
        self.invoke_url = f"{self.base_url}/generate"
        self.stream_url = f"{self.base_url}/generate_stream"
        print(f"✅ SimpleLLMService initialized for endpoint: {self.base_url}")

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """
        Sends a request to the non-streaming endpoint and returns the complete text response.
        
        Args:
            prompt (str): The prompt to send to the model.
            **kwargs: Additional generation parameters (e.g., temperature, max_tokens).

        Returns:
            str: The generated text from the model.
        """
        payload = {"prompt": prompt, **kwargs}
        try:
            response = requests.post(self.invoke_url, json=payload, timeout=60)
            response.raise_for_status()
            response_data = response.json()
            return response_data.get("text", "")
        except requests.exceptions.RequestException as e:
            print(f"\n[Error] An error occurred during invoke: {e}")
            raise

    def stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """
        Connects to the streaming endpoint and yields text chunks as they arrive.
        This is a synchronous generator.

        Args:
            prompt (str): The prompt to send to the model.
            **kwargs: Additional generation parameters (e.g., temperature, max_tokens).

        Yields:
            Generator[str, None, None]: A generator that yields text chunks.
        """
        payload = {"prompt": prompt, **kwargs}
        try:
            # The key is the 'stream=True' parameter.
            # This tells 'requests' not to download the whole body at once.
            with requests.post(self.stream_url, json=payload, timeout=60, stream=True) as response:
                response.raise_for_status()
                
                # iter_content() with chunk_size=None will read chunks as they come in.
                # We decode the byte chunks into strings.
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        yield chunk
                        
        except requests.exceptions.RequestException as e:
            print(f"\n[Error] An error occurred during stream: {e}")
            raise


# #-------------------------------------------------------------------------------------
# # Assuming the SimpleLLMService class is in this file or imported.

# def main():
#     """
#     Demonstrates the usage of the simple, synchronous service.
#     """
#     # Initialize the service client
#     service = LLMService(base_url="http://localhost:24434")

#     # --- 1. Test the synchronous invoke() method ---
#     print("--- 1. Testing invoke() method ---")
#     try:
#         invoke_prompt = "Write a short, dramatic story about a lonely lighthouse keeper who discovers a message in a bottle."
#         response_text = service.invoke(
#             prompt=invoke_prompt,
#             temperature=0.8,
#             max_tokens=256
#         )
#         print("\n[Full Response from invoke()]:")
#         print(response_text)
#     except Exception as e:
#         print(f"\n[Invoke Failed]: {e}")
        
#     print("\n" + "="*50 + "\n")

#     # --- 2. Test the synchronous stream() method ---
#     print("--- 2. Testing stream() method ---")
#     try:
#         stream_prompt = "What are the three most important features of the NVIDIA A6000 GPU for AI?"
        
#         print(f"\n[Streaming Response for: '{stream_prompt}']:")
#         # Use a simple 'for' loop to consume the generator
#         full_response = []
#         for chunk in service.stream(
#             prompt=stream_prompt,
#             temperature=0.2,
#             max_tokens=150
#         ):
#             print(chunk, end="", flush=True)
#             full_response.append(chunk)

#         print("\n--- Stream finished ---")
#         # You can still assemble the full response if you need it
#         # final_text = "".join(full_response)
        
#     except Exception as e:
#         print(f"\n[Stream Failed]: {e}")


# if __name__ == "__main__":
#     main()