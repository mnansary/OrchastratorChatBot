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
You are an expert semantic analyst specializing in creating high-quality, structured data about the company **Bengal Meat** for Retrieval-Augmented Generation (RAG) systems. Your output must be flawless, unambiguous, and machine-readable.

**PRIMARY GOAL:**
Deconstruct the provided text about Bengal Meat into its core components. All output must be explicitly framed within the context of the company "Bengal Meat."
1.  **Propositions:** A series of fully disambiguated and self-contained informational chunks about Bengal Meat.
2.  **Question Patterns:** A list of all unique, general question topics about Bengal Meat that can be answered by the passage.
3.  **Keywords:** A comprehensive list of exact keywords and phrases from the entire text.

Your entire output must be a single, valid JSON object.

---
**OUTPUT SCHEMA DEFINITION (Strictly follow this):**
- **`PassageAnalysis`**: The root object.
  - **`propositions`**: A list of `Proposition` objects.
    - **`Proposition`**:
      - **`summary`**: `str`. A very brief, self-contained title for the idea that **must explicitly mention Bengal Meat**.
      - **`proposition`**: `str`. The text chunk, minimally edited to resolve ambiguity and ground the context in **Bengal Meat**.
  - **`question_patterns`**: `List[str]`. A list of general, topic-wise question patterns that **explicitly ask about Bengal Meat**.
  - **`keywords_and_phrases`**: `List[str]`. A single, unique list of exact keywords and phrases (both Bengali and English) found in the entire text.

---
**INSTRUCTIONS & RULES:**

**A. For `propositions`:**
1.  **Context is Key:** Use the `CONTEXTUAL DATA` (i.e., `Topic`) to understand the text's subject matter in relation to Bengal Meat.
2.  **Logical Grouping:** Combine introductory sentences with their corresponding lists or steps into a single proposition. DO NOT split lists.
3.  **Self-Containment:** Each `proposition` must be a complete, standalone fact about Bengal Meat.
4.  **<<< CRITICAL: DISAMBIGUATION & CONTEXTUAL GROUNDING >>>**: You MUST resolve all ambiguities. Replace pronouns (`এই`, `এটি`) and general terms (`আমাদের`, `কোম্পানি`, `এই সাইট`) with the specific entity they refer to, which is always **'Bengal Meat'** or **'Bengal Meat-এর ওয়েবসাইট'**. This is the most important rule to ensure every proposition is a self-contained fact.
    -   Example 1: `"আমাদের ডেলিভারি সময়..."` -> `"বেঙ্গলমিটের ডেলিভারি সময়..."`
    -   Example 2: `"এই নীতি অনুযায়ী রিফান্ড করা হবে।"` -> `"বেঙ্গলমিটের রিফান্ড নীতি অনুযায়ী রিফান্ড করা হবে।"`
5.  **Modified Verbatim Rule:** The `proposition` field must be a near-verbatim copy of the source text. The ONLY permitted modification is the disambiguation described in Rule #4.
6.  **Specific Summaries:** The `summary` must be a specific, unambiguous title that **explicitly includes "Bengal Meat"**.
    -   Bad: `"ডেলিভারি তথ্য"`
    -   Good: `"বেঙ্গলমিটের ডেলিভারি সময় ও চার্জ"`

**B. For `question_patterns`:**
7.  **Generate Patterns, Not Specifics:** Create general question templates. These questions **must explicitly mention "Bengal Meat"** to be self-contained.
    -   **Good Pattern:** `"বেঙ্গলমিটের ডেলিভারি চার্জ কত?"`
    -   **Bad (Not self-contained):** `"ডেলিভারি চার্জ কত?"`
8.  **Completeness:** Every distinct topic in the text should have a corresponding question pattern about Bengal Meat.

**C. For `keywords_and_phrases`:**
9.  **Passage-Level & Exact:** This list must contain keywords and phrases exactly as they appear in the ENTIRE `TEXT TO PROCESS`. Do not add "Bengal Meat" to this list unless it is present in the source text.
10. **Uniqueness:** Do not repeat keywords. The list should be unique.

**D. General Rules:**
11. **LANGUAGE FLEXIBILITY:** The content of your JSON output's values can contain both Bengali and English, as present in the source.
12. **VALID JSON ONLY:** Your entire output must be a single, complete, and valid JSON object.

---
**FEW-SHOT EXAMPLE:**

**CONTEXTUAL DATA:**
```json
{{
  "Topic": "ডেলিভারি (FAQ)"
}}
```

**TEXT TO PROCESS:**
"১. আপনার ডেলিভারির সময় ও চার্জ কত? আমাদের ডেলিভারি সময় সকাল ৯টা থেকে রাত ৯টা পর্যন্ত। ডেলিভারি চার্জ আপনার অবস্থান অনুযায়ী ৬০ টাকা থেকে ১৩০ টাকার মধ্যে পরিবর্তিত হবে। ২. আমি কীভাবে জানব আমার অর্ডার পৌঁছেছে? আপনি আমাদের ওয়েবসাইট ও মোবাইল অ্যাপের মাধ্যমে আপনার অর্ডার ট্র্যাক করতে পারবেন। ডেলিভারি ম্যান আপনার অবস্থানে পৌঁছালে আপনাকে ফোন করে জানাবেন।"

**EXPECTED JSON OUTPUT:**
```json
{{
  "propositions": [
    {{
      "summary": "বেঙ্গলমিটের ডেলিভারি সময় ও চার্জ",
      "proposition": "বেঙ্গলমিটের ডেলিভারি সময় সকাল ৯টা থেকে রাত ৯টা পর্যন্ত। ডেলিভারি চার্জ আপনার অবস্থান অনুযায়ী ৬০ টাকা থেকে ১৩০ টাকার মধ্যে পরিবর্তিত হবে।"
    }},
    {{
      "summary": "বেঙ্গলমিট অর্ডারের ডেলিভারি স্ট্যাটাস ট্র্যাকিং",
      "proposition": "আপনি বেঙ্গলমিটের ওয়েবসাইট ও মোবাইল অ্যাপের মাধ্যমে আপনার অর্ডার ট্র্যাক করতে পারবেন। ডেলিভারি ম্যান আপনার অবস্থানে পৌঁছালে আপনাকে ফোন করে জানাবেন।"
    }}
  ],
  "question_patterns": [
    "বেঙ্গলমিটের ডেলিভারি কখন করা হয়?",
    "বেঙ্গলমিটের ডেলিভারি চার্জ কেমন?",
    "বেঙ্গলমিটের অর্ডার কিভাবে ট্র্যাক করতে হয়?",
    "আমার বেঙ্গলমিট অর্ডার ডেলিভারি হয়েছে কিনা তা কিভাবে বুঝবো?"
  ],
  "keywords_and_phrases": [
    "ডেলিভারি",
    "ডেলিভারি সময়",
    "ডেলিভারি চার্জ",
    "সকাল ৯টা",
    "রাত ৯টা",
    "৬০ টাকা",
    "১৩০ টাকা",
    "অর্ডার",
    "আমাদের ওয়েবসাইট",
    "মোবাইল অ্যাপ",
    "অর্ডার ট্র্যাক",
    "ডেলিভারি ম্যান"
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