# core/imageprompts.py

# Prompt for standard OCR: Asks the model to transcribe all text from the image.
OCR_PROMPT = """
Analyze the image provided and perform Optical Character Recognition (OCR).
Transcribe all text visible in the image accurately.
Present the extracted text clearly. If there are distinct blocks of text, format them logically.
"""

# Prompt for answering a specific question about the image.
# The user's question will be formatted into this string.
QA_PROMPT = """
You are an expert at analyzing images and documents.
Based on the provided image, please answer the following question:

Question: "{user_question}"

First, analyze the image to understand its content, then provide a concise and accurate answer based only on the information visible in the image.
"""