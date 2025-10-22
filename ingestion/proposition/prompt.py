# prompt.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from google.genai import types
import json

# --------------------------------------------------------------------------
# 1. DEFINE THE OUTPUT SCHEMA (PYDANTIC MODELS)
# (This section has been updated for the new output structure)
# --------------------------------------------------------------------------

class Proposition(BaseModel):
    """
    A model to represent a single, self-contained idea or proposition
    extracted from a larger text.
    """
    summary: str = Field(
        ...,
        description="A very brief, concise title or topic for the proposition's core idea. Must be in the same language as the text (Bengali)."
    )
    proposition: str = Field(
        ...,
        description="The extracted, self-contained sentence or group of sentences from the original text that forms a complete idea. Must be a verbatim quote from the text, with minor edits only to resolve ambiguity."
    )

class PassageAnalysis(BaseModel):
    """
    A structured model containing a complete analysis of the source text,
    including semantic chunks, question patterns, and keywords.
    """
    propositions: List[Proposition] = Field(
        ...,
        description="A complete list of self-contained ideas and propositions extracted from the original text."
    )
    question_patterns: List[str] = Field(
        ...,
        description="A list of general, topic-wise, unique, and self-contained question patterns (in Bengali) that can be fully answered by the provided text."
    )
    keywords_and_phrases: List[str] = Field(
        ...,
        description="A unique list of all exact keywords and key phrases (in Bengali) present in the entire passage. This list is for the whole passage, not specific to any single proposition."
    )

# --------------------------------------------------------------------------
# 2. DEFINE THE GENERATION CONFIGURATION
# (This section is correct and requires no changes)
# --------------------------------------------------------------------------

def _resolve_schema_references(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively resolves '$ref' pointers in a JSON Schema.
    """
    defs = schema.get('$defs', {})

    def _resolver(obj):
        if isinstance(obj, dict):
            if '$ref' in obj:
                ref_key = obj['$ref'].split('/')[-1]
                return _resolver(defs.get(ref_key, {}))
            return {k: _resolver(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_resolver(item) for item in obj]
        return obj

    resolved_schema = _resolver(schema)
    if '$defs' in resolved_schema:
        del resolved_schema['$defs']
    return resolved_schema

def _clean_schema_for_api(schema: Dict) -> Dict:
    """
    Recursively removes keys from a schema that are not supported by the API.
    """
    if isinstance(schema, dict):
        cleaned = {k: _clean_schema_for_api(v) for k, v in schema.items() if k not in ['title', 'description']}
        return cleaned
    elif isinstance(schema, list):
        return [_clean_schema_for_api(item) for item in schema]
    return schema

# --- Schema Processing Pipeline ---
raw_schema = PassageAnalysis.model_json_schema()
resolved_schema = _resolve_schema_references(raw_schema)
final_schema_for_api = _clean_schema_for_api(resolved_schema)

generation_config=types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=final_schema_for_api,
    temperature=0.0,
    max_output_tokens=60000,
    top_p=0.95,
)
# --------------------------------------------------------------------------
# 3. DEFINE THE PROMPT CREATION FUNCTION (HEAVILY MODIFIED SECTION)
# --------------------------------------------------------------------------

def create_prompt(passage_data: Dict[str, Any]) -> str:
    """
    Injects passage data into the main analysis prompt template.

    Args:
        passage_data (Dict[str, Any]): A dictionary representing one row of data.

    Returns:
        str: The final, complete prompt ready to be sent to the LLM.

    Raises:
        ValueError: If the input passage_data or its 'Text' field is empty.
    """
    if not passage_data or not passage_data.get('Text', '').strip():
        raise ValueError("The input passage_data dictionary or its 'Text' field cannot be empty.")

    # Exclude 'Text' from the context JSON, as it's passed separately
    context_str = json.dumps(
        {k: v for k, v in passage_data.items() if k != 'Text'},
        ensure_ascii=False,
        indent=2
    )
    
    text_to_process = passage_data['Text']

    return f"""
**ROLE:**
You are an expert semantic analyst specializing in creating high-quality, structured data from text for Retrieval-Augmented Generation (RAG) systems. Your output must be flawless, unambiguous, and machine-readable.

**PRIMARY GOAL:**
Deconstruct the provided Bengali text into its core components:
1.  **Propositions:** A series of fully disambiguated and self-contained informational chunks.
2.  **Question Patterns:** A list of all unique, general question topics that can be answered by the passage.
3.  **Keywords:** A comprehensive list of exact keywords and phrases from the entire text.

Your entire output must be a single, valid JSON object in pure Bengali.

---
**OUTPUT SCHEMA DEFINITION (Strictly follow this):**
- **`PassageAnalysis`**: The root object.
  - **`propositions`**: A list of `Proposition` objects.
    - **`Proposition`**:
      - **`summary`**: `str`. A very brief, self-contained, and specific topic or title for the idea in Bengali.
      - **`proposition`**: `str`. The text chunk from the source, minimally edited ONLY to resolve ambiguity.
  - **`question_patterns`**: `List[str]`. A list of general, topic-wise Bengali question patterns answerable by the text.
  - **`keywords_and_phrases`**: `List[str]`. A single, unique list of exact Bengali keywords and phrases found in the entire text.

---
**INSTRUCTIONS & RULES:**

**A. For `propositions`:**
1.  **Context is Key:** Use the `CONTEXTUAL DATA` (e.g., `Service`, `Topic`) to understand the text's subject matter.
2.  **Logical Grouping:** Combine introductory sentences with their corresponding lists or steps into a single proposition. DO NOT split lists or procedural steps.
3.  **Self-Containment:** Each `proposition` and its `summary` must be a complete, standalone idea.
4.  **<<< CRITICAL: DISAMBIGUATION >>>**: You MUST resolve ambiguous references. Replace pronouns (`এই`, `এটি`) and vague phrases (`এই সেবা`) with the specific noun they refer to, using the `CONTEXTUAL DATA`.
    -   Example: `"আপনি রেজিস্ট্রেশন করে এই ওয়েবসাইটের সুবিধা নিতে পারেন।"` -> `"আপনি রেজিস্ট্রেশন করে বাংলাদেশ নির্বাচন কমিশনের এনআইডি ওয়েবসাইটের সুবিধা নিতে পারেন।"`
5.  **Modified Verbatim Rule:** The `proposition` field must be a near-verbatim copy of the source text. The ONLY permitted modification is the disambiguation described in Rule #4.
6.  **Specific Summaries:** The `summary` must be a specific, unambiguous title.
    -   Bad: `"রেজিস্ট্রেশন প্রক্রিয়া"`
    -   Good: `"এনআইডি ওয়েবসাইট ভোটার রেজিস্ট্রেশন প্রক্রিয়া"`

**B. For `question_patterns`:**
7.  **Generate Patterns, Not Specifics:** Create general question templates that cover all topics in the text. These should be broad enough to represent a user's general intent.
    -   **Good Pattern:** `"স্মার্ট কার্ডের স্ট্যাটাস চেক করার উপায় কি?"`
    -   **Bad (Too Specific):** `"আমার এনআইডি নম্বর ১২৩৪৫ দিয়ে স্মার্ট কার্ডের স্ট্যাটাস কিভাবে চেক করবো?"`
8.  **Completeness:** Every distinct topic or piece of information in the text should have a corresponding question pattern.

**C. For `keywords_and_phrases`:**
9.  **Passage-Level & Exact:** This list must contain keywords and phrases from the ENTIRE `TEXT TO PROCESS`. It is a single list for the whole passage.
10. **Uniqueness:** Do not repeat keywords. The list should be unique.

**D. General Rules:**
11. **<<< CRITICAL: LANGUAGE PURITY >>>**: The entire content of your JSON output MUST be in the Bengali language. Do not include tokens from any other language.
12. **VALID JSON ONLY:** Your entire output must be a single, complete, and valid JSON object.

---
**FEW-SHOT EXAMPLE:**

**CONTEXTUAL DATA:**
```json
{{
  "Alternate_names": "এন আই ডি, এনাইডি, ...",
  "Category": "স্মার্ট কার্ড ও জাতীয়পরিচয়পত্র",
  "Keyword": "এনআইডি",
  "Service": "স্মার্ট কার্ড",
  "Topic": "স্মার্ট কার্ড যেভাবে পাওয়া যাবে"
}}
```

**TEXT TO PROCESS:**
"জাতীয় পরিচয়পত্রের নিরাপদ ও সহজ ব্যবহারযোগ্যতা নিশ্চিত করতে এতে যুক্ত করা হয়েছে একটি মাইক্রো চিপ, যা মুহূর্তের মধ্যে একজন নাগরিকের পরিচয় প্রদান করে। আর এই মাইক্রোচিপের মধ্যে নাগরিক সম্পর্কিত যাবতীয় তথ্য নিবদ্ধ থাকার কারণে এটিকে বলা হয় স্মার্ট কার্ড। আপনি ভোটার হয়েছেন কিন্তু এখনো স্মার্ট এন আই ডি কার্ড (Smart NID Card) পাননি, তাহলে অপেক্ষা করতে হবে। বাংলাদেশ নির্বাচন কমিশন থেকে মাত্র ১ কোটি ভোটারদের মাঝে স্মার্ট আইডি বিতরণ করা হয়েছে। আপনার স্মার্ট আইডি কার্ড তৈরি হলে ইউনিয়ন পরিষদ বা সিটি কর্পোরেশন থেকে সেটি সংগ্রহ করতে পারবেন।"

**EXPECTED JSON OUTPUT:**
```json
{{
  "propositions": [
    {{
      "summary": "স্মার্ট কার্ডের সংজ্ঞা ও মাইক্রো চিপের কার্যকারিতা",
      "proposition": "জাতীয় পরিচয়পত্রের নিরাপদ ও সহজ ব্যবহারযোগ্যতা নিশ্চিত করতে জাতীয় পরিচয়পত্রে যুক্ত করা হয়েছে একটি মাইক্রো চিপ, যা মুহূর্তের মধ্যে একজন নাগরিকের পরিচয় প্রদান করে। আর এই মাইক্রোচিপের মধ্যে নাগরিক সম্পর্কিত যাবতীয় তথ্য নিবদ্ধ থাকার কারণে জাতীয় পরিচয়পত্রটিকে বলা হয় স্মার্ট কার্ড।"
    }},
    {{
      "summary": "স্মার্ট কার্ড না পাওয়ার ক্ষেত্রে করণীয়",
      "proposition": "আপনি ভোটার হয়েছেন কিন্তু এখনো স্মার্ট এন আই ডি কার্ড (Smart NID Card) পাননি, তাহলে অপেক্ষা করতে হবে।"
    }},
    {{
      "summary": "বাংলাদেশে স্মার্ট কার্ড বিতরণের বর্তমান অবস্থা",
      "proposition": "বাংলাদেশ নির্বাচন কমিশন থেকে মাত্র ১ কোটি ভোটারদের মাঝে স্মার্ট আইডি বিতরণ করা হয়েছে।"
    }},
    {{
      "summary": "স্মার্ট কার্ড সংগ্রহের নির্ধারিত স্থান",
      "proposition": "আপনার স্মার্ট আইডি কার্ড তৈরি হলে ইউনিয়ন পরিষদ বা সিটি কর্পোরেশন থেকে স্মার্ট আইডি কার্ডটি সংগ্রহ করতে পারবেন।"
    }}
  ],
  "question_patterns": [
    "স্মার্ট কার্ড কি এবং কেন এটিকে স্মার্ট কার্ড বলা হয়?",
    "স্মার্ট কার্ডের মাইক্রো চিপের কাজ কি?",
    "ভোটার হওয়ার পরেও স্মার্ট কার্ড না পেলে করণীয় কি?",
    "বাংলাদেশ নির্বাচন কমিশন কতগুলো স্মার্ট কার্ড বিতরণ করেছে?",
    "তৈরি হওয়া স্মার্ট কার্ড কোথা থেকে সংগ্রহ করতে হয়?"
  ],
  "keywords_and_phrases": [
    "জাতীয় পরিচয়পত্র",
    "মাইক্রো চিপ",
    "নাগরিকের পরিচয়",
    "স্মার্ট কার্ড",
    "ভোটার",
    "স্মার্ট এন আই ডি কার্ড",
    "Smart NID Card",
    "বাংলাদেশ নির্বাচন কমিশন",
    "স্মার্ট আইডি বিতরণ",
    "ইউনিয়ন পরিষদ",
    "সিটি কর্পোরেশন"
  ]
}}
```
---
**PASSAGE FOR ANALYSIS:**

**CONTEXTUAL DATA:**
```json
{context_str}
```

**TEXT TO PROCESS:**
{text_to_process}

**YOUR JSON OUTPUT:**
"""