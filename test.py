import requests
import json

# The endpoint for non-streaming generation
url = "http://localhost:24434/generate"

# Define the prompt and control parameters
payload = {
    "prompt": "Write a short, dramatic story about a lonely lighthouse keeper who discovers a message in a bottle.",
    "temperature": 0.8,
    "max_tokens": 256,
    "repetition_penalty": 1.15
}

print("Sending request...")
try:
    # Make the POST request
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

    # Print the clean JSON response
    response_data = response.json()
    print("\n--- Full Response Received ---")
    print(json.dumps(response_data, indent=2))

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")