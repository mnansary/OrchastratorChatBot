# core/LLMservice.py

import requests
import json
import base64
import os
from dotenv import load_dotenv
from typing import Generator, Dict, Any

load_dotenv()

class LLMService:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.chat_url = f"{self.base_url}/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        print(f"✅ LLMService initialized for model '{self.model}' at endpoint: {self.chat_url}")

    def _process_stream(self, response: requests.Response) -> Generator[str, None, None]:
        # (This method is unchanged)
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
        """Sends a request for a single, complete response (non-streaming)."""
        messages = [{"role": "user", "content": prompt}]
        payload = {"model": self.model, "messages": messages, "stream": False, **kwargs}
        
        print(f"--- Sending payload to LLM: {json.dumps(payload, indent=2)} ---") # DEBUG PRINT
        
        try:
            response = requests.post(self.chat_url, headers=self.headers, json=payload, timeout=120)
            
            # ========== START OF CRUCIAL DEBUG BLOCK ==========
            #print(f"LLM API Status Code: {response.status_code}")
            #print(f"LLM API Raw Response Text: '{response.text}'")
            # ==========  END OF CRUCIAL DEBUG BLOCK  ==========

            response.raise_for_status() # This will now raise an error for 4xx/5xx status codes
            
            response_data = response.json()
            
            # Check if the response structure is valid before accessing keys
            if "choices" in response_data and response_data["choices"]:
                message = response_data["choices"][0].get("message", {})
                content = message.get("content", "")
                return content
            else:
                print("❌ ERROR: LLM response is missing 'choices' array.")
                return "" # Return empty if structure is wrong

        except requests.exceptions.HTTPError as e:
            print(f"\n[Error] HTTP Error during invoke: {e}")
            print(f"Response Body: {e.response.text}")
            return "" # Return empty on HTTP error
        except requests.exceptions.RequestException as e:
            print(f"\n[Error] Network error during invoke: {e}")
            return "" # Return empty on network error
        except json.JSONDecodeError:
            print(f"\n[Error] Failed to decode JSON from LLM response.")
            return "" # Return empty if response is not JSON

    # stream and image_stream methods remain unchanged
    def stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """Connects to the streaming endpoint and yields text chunks as they arrive."""
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
        """Sends an image and a text prompt for a streaming response."""
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            print(f"\n[Error] Image file not found at: {image_path}")
            raise

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