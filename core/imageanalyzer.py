# core/imageanalyzer.py

import os
from typing import Generator
from .LLMservice import LLMService
from .imageprompts import OCR_PROMPT, QA_PROMPT
from dotenv import load_dotenv
load_dotenv()
# Ensure you have a .env file in your root directory with these variables
# OPENAI_API_KEY="your_api_key_here"
# OPENAI_API_BASE="your_base_url_here"
# OPENAI_MODEL="gpt-4o" # Or another multimodal model

class ImageAnalyzer:
    """
    Handles the logic for analyzing images using the LLMService.
    """
    def __init__(self):
        """
        Initializes the ImageAnalyzer and the LLMService.
        """
        api_key = os.getenv("LLM_MODEL_API_KEY")
        base_url = os.getenv("LLM_MODEL_BASE_URL") # Default to OpenAI's public API
        model = os.getenv("LLM_MODEL_NAME") # gpt-4o is a good default for this

        if not api_key:
            raise ValueError("API key not found. Please set OPENAI_API_KEY in your .env file.")

        self.llm_service = LLMService(api_key=api_key, base_url=base_url, model=model)
        print("✅ ImageAnalyzer initialized.")

    def analyze_image(self, image_path: str, question: str = None) -> Generator[str, None, None]:
        """
        Analyzes an image and returns a stream of text.

        Args:
            image_path (str): The local path to the image file.
            question (str, optional): A specific question to ask about the image.
                                      If None, performs standard OCR. Defaults to None.

        Returns:
            Generator[str, None, None]: A generator that yields the text response chunks.
        """
        if question and question.strip():
            # If a question is provided, format it into the QA_PROMPT
            prompt = QA_PROMPT.format(user_question=question)
            print(f"--- Sending Image with Question: '{question}' ---")
        else:
            # If no question is provided, use the standard OCR_PROMPT
            prompt = OCR_PROMPT
            print("--- Sending Image for Standard OCR ---")

        try:
            # The image_stream method handles sending the image and prompt
            response_generator = self.llm_service.image_stream(
                prompt=prompt,
                image_path=image_path,
                max_tokens=1024 # Limit the response length
            )
            yield from response_generator
        except FileNotFoundError:
            # Yield an error message if the file doesn't exist
            yield f"Error: The image file was not found at {image_path}"
        except Exception as e:
            # Yield any other exception messages
            yield f"An unexpected error occurred: {e}"