# --- START OF FINAL CORRECTED FILE: cogops/models/qwen3async_llm.py ---

import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI, APIError, BadRequestError, APIConnectionError, APITimeoutError
from typing import Any, Type, TypeVar, AsyncGenerator, List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from pydantic import BaseModel, Field
from cogops.utils.prompt import build_structured_prompt
from cogops.tools.tools import tools_list, available_tools_map

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PydanticModel = TypeVar("PydanticModel", bound=BaseModel)

class ContextLengthExceededError(Exception):
    pass

RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError)

# --- NEW: Centralized list of all tools that require session_meta ---
# REASON: This makes the tool-calling logic scalable. To make another tool
# session-aware, you only need to add its name to this list.
SESSION_AWARE_TOOLS = [
    "get_user_order_profile_as_markdown",
    "get_promotional_products"
]

def log_retry_attempt(retry_state):
    logging.warning(
        f"LLM API call failed with {retry_state.outcome.exception()}, "
        f"retrying in {retry_state.next_action.sleep} seconds... "
        f"(Attempt {retry_state.attempt_number})"
    )

class AsyncLLMService:
    def __init__(self, api_key: str, model: str, base_url: str, max_context_tokens: int):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.model = model
        self.max_context_tokens = max_context_tokens
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        logging.info(f"✅ AsyncLLMService initialized for model '{self.model}' with max_tokens={self.max_context_tokens}.")

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=log_retry_attempt
    )
    async def stream_with_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        available_tools: Dict[str, callable],
        session_meta: Dict[str, Any],
        **kwargs: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            logging.info("   [Step 1: Streaming model response...]")
            stream = await self.client.chat.completions.create(
                model=self.model, messages=messages, tools=tools, tool_choice="auto", stream=True, **kwargs
            )
            response_message = {"role": "assistant", "content": "", "tool_calls": []}
            tool_call_index_map = {}
            async for chunk in stream:
                if not chunk.choices: continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield {"type": "answer_chunk", "content": delta.content}
                    if response_message["content"] is not None:
                         response_message["content"] += delta.content
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        index = tc_delta.index
                        if index not in tool_call_index_map:
                            tool_call_index_map[index] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                        if tc_delta.id: tool_call_index_map[index]["id"] += tc_delta.id
                        if tc_delta.function and tc_delta.function.name: tool_call_index_map[index]["function"]["name"] += tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments: tool_call_index_map[index]["function"]["arguments"] += tc_delta.function.arguments
            if tool_call_index_map:
                response_message["tool_calls"] = list(tool_call_index_map.values())
            tool_calls = response_message["tool_calls"]
            if not tool_calls:
                return

            logging.info(f"   [Step 2: Model requested {len(tool_calls)} tool call(s)...]")
            messages.append(response_message)
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                yield {"type": "tool_call", "tool_name": function_name}
                function_to_call = available_tools.get(function_name)
                if function_to_call:
                    try:
                        function_args = json.loads(tool_call["function"]["arguments"] or "{}")
                        
                        # --- CRITICAL FIX: Use the generalized list for injection ---
                        # REASON: The previous hardcoded 'if' statement was not scalable.
                        # This dynamically checks if the called tool is in our list of
                        # session-aware tools and injects the context if required.
                        if function_name in SESSION_AWARE_TOOLS:
                            function_args['session_meta'] = session_meta
                        # --- END OF FIX ---
                            
                        if asyncio.iscoroutinefunction(function_to_call):
                            function_response = await function_to_call(**function_args)
                        else:
                            function_response = await asyncio.to_thread(function_to_call, **function_args)
                        messages.append({"tool_call_id": tool_call["id"], "role": "tool", "name": function_name, "content": str(function_response)})
                    except Exception as e:
                        logging.error(f"Error executing tool '{function_name}': {e}", exc_info=True)
                        messages.append({"tool_call_id": tool_call["id"], "role": "tool", "name": function_name, "content": f"Error: Tool execution failed."})
                else:
                    logging.warning(f"Model tried to call an unknown tool: {function_name}")

            logging.info("   [Step 3: Streaming final answer...]")
            final_stream = await self.client.chat.completions.create(
                model=self.model, messages=messages, stream=True, **kwargs
            )
            async for chunk in final_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {"type": "answer_chunk", "content": chunk.choices[0].delta.content}
        except BadRequestError as e:
            if "context length" in str(e).lower() or "too large" in str(e).lower():
                logging.error(f"FATAL: Prompt exceeded context window.")
                yield {"type": "error", "content": "Conversation too long. Please start a new session."}
                raise ContextLengthExceededError(f"Prompt is too long.") from e
            else:
                logging.error(f"A non-retryable bad request error occurred: {e}", exc_info=True)
                yield {"type": "error", "content": "There was an issue processing your request."}
                raise
        except Exception as e:
            logging.error(f"An unexpected error occurred during streaming tool invocation: {e}", exc_info=True)
            yield {"type": "error", "content": "An internal error occurred."}
            raise

# --- END OF FINAL CORRECTED FILE: cogops/models/qwen3async_llm.py ---