import json
from typing import Type
from pydantic import BaseModel

def build_structured_prompt(prompt: str, response_model: Type[BaseModel]) -> str:
    """
    Constructs a standardized prompt for forcing a model to generate a
    JSON object that conforms to a given Pydantic model's schema.
    
    Args:
        prompt (str): The core user prompt or request.
        response_model (Type[BaseModel]): The Pydantic model for the desired output.

    Returns:
        str: A fully formatted prompt ready for an LLM.
    """
    # Generate the JSON schema from the Pydantic model.
    schema = json.dumps(response_model.model_json_schema(), indent=2)

    # Engineer a new prompt that includes the original prompt and instructions.
    structured_prompt = f"""
    Given the following request:
    ---
    {prompt}
    ---
    Your task is to provide a response as a single, valid JSON object that strictly adheres to the following JSON Schema.
    Do not include any extra text, explanations, or markdown formatting (like ```json) outside of the JSON object itself.

    JSON Schema:
    {schema}
    """
    return structured_prompt