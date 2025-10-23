import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI, APIError, BadRequestError
from typing import Any, Type, TypeVar, AsyncGenerator, List, Dict
from pydantic import BaseModel, Field
from cogops.utils.prompt import build_structured_prompt
from cogops.tools.tools import tools_list, available_tools_map
# Load environment variables and set up logging
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PydanticModel = TypeVar("PydanticModel", bound=BaseModel)

class ContextLengthExceededError(Exception):
    """Custom exception for when a prompt exceeds the model's context window."""
    pass

class AsyncLLMService:
    """
    An ASYNCHRONOUS client for OpenAI-compatible APIs.
    """
    def __init__(self, api_key: str, model: str, base_url: str, max_context_tokens: int):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        
        self.model = model
        self.max_context_tokens = max_context_tokens
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        
        print(f"✅ AsyncLLMService initialized for model '{self.model}' with max_tokens={self.max_context_tokens}.")

    async def invoke(self, prompt: str, **kwargs: Any) -> str:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = await self.client.chat.completions.create(model=self.model, messages=messages, **kwargs)
            return response.choices[0].message.content or ""
        except BadRequestError as e:
            if "context length" in str(e).lower() or "too large" in str(e).lower():
                logging.error(f"Prompt exceeded context window for model {self.model}.")
                raise ContextLengthExceededError(f"Prompt is too long for the model's {self.max_context_tokens} token limit.") from e
            else:
                logging.error(f"Unhandled BadRequestError during invoke: {e}")
                raise
        except Exception as e:
            logging.error(f"An error occurred during invoke: {e}", exc_info=True)
            raise

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        messages = [{"role": "user", "content": prompt}]
        try:
            stream = await self.client.chat.completions.create(model=self.model, messages=messages, stream=True, **kwargs)
            async for chunk in stream:
                content_chunk = chunk.choices[0].delta.content if chunk.choices else None
                if content_chunk:
                    yield content_chunk
        except BadRequestError as e:
            if "context length" in str(e).lower() or "too large" in str(e).lower():
                logging.error(f"Prompt exceeded context window for model {self.model}.")
                raise ContextLengthExceededError(f"Prompt is too long for the model's {self.max_context_tokens} token limit.") from e
            else:
                logging.error(f"Unhandled BadRequestError during stream: {e}")
                raise
        except Exception as e:
            logging.error(f"An error occurred during stream: {e}", exc_info=True)
            raise

    async def invoke_structured(
        self, prompt: str, response_model: Type[PydanticModel], **kwargs: Any
    ) -> PydanticModel:
        # --- MODIFIED: Use the shared utility function ---
        structured_prompt = build_structured_prompt(prompt, response_model)
        messages = [{"role": "user", "content": structured_prompt}]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, response_format={"type": "json_object"}, **kwargs
            )
            json_response_str = response.choices[0].message.content
            if not json_response_str:
                raise ValueError("The model returned an empty response.")
            return response_model.model_validate_json(json_response_str)
        except BadRequestError as e:
            if "context length" in str(e).lower() or "too large" in str(e).lower():
                logging.error(f"Prompt exceeded context window for model {self.model}.")
                raise ContextLengthExceededError(f"Prompt is too long for the model's {self.max_context_tokens} token limit.") from e
            else:
                logging.error(f"Unhandled BadRequestError during structured invoke: {e}")
                raise
        except Exception as e:
            logging.error(f"An error occurred during structured invoke: {e}", exc_info=True)
            raise

    async def invoke_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        available_tools: Dict[str, callable],
        **kwargs: Any  # <-- FIX: Accept kwargs
    ) -> str:
        """Handles a multi-step conversation with tool-calling capabilities asynchronously."""
        try:
            print("\n   [Step 1: Asking model if a tool is needed...]")
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, tools=tools, tool_choice="auto", **kwargs # <-- FIX: Pass kwargs
            )
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            if not tool_calls:
                print("   [Model responded directly without using a tool.]")
                return response_message.content or ""

            print("   [Step 2: Model requested a tool call. Executing it...]")
            messages.append(response_message)
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = available_tools.get(function_name)
                
                if function_to_call:
                    function_args = json.loads(tool_call.function.arguments or "{}")
                    if asyncio.iscoroutinefunction(function_to_call):
                        function_response = await function_to_call(**function_args)
                    else:
                        function_response = function_to_call(**function_args)
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_response),
                    })
                else:
                    logging.warning(f"Model tried to call an unknown tool: {function_name}")
            
            print("   [Step 3: Sending tool result back to model for final answer...]")
            second_response = await self.client.chat.completions.create(
                model=self.model, messages=messages, **kwargs # <-- FIX: Pass kwargs
            )
            return second_response.choices[0].message.content or "Model did not provide a final response."
        except Exception as e:
            logging.error(f"An error occurred during tool invocation: {e}", exc_info=True)
            raise

    # FILE: models/qwen3async_llm.py

    async def stream_with_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        available_tools: Dict[str, callable],
        session_meta: Dict[str, Any],  # Add session_meta to the signature
        **kwargs: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Handles a multi-step conversation with tool-calling capabilities, streaming structured JSON events.
        This is the core of the agent's reasoning and action loop.
        """
        try:
            logging.info("   [Step 1: Streaming model response to check for tool calls...]")

            # === FIRST LLM CALL: Check if a tool is needed or if the model can answer directly ===
            stream = await self.client.chat.completions.create(
                model=self.model, messages=messages, tools=tools, tool_choice="auto", stream=True, **kwargs
            )

            # Prepare to reconstruct the full message from streamed chunks
            response_message = {"role": "assistant", "content": "", "tool_calls": []}
            tool_call_index_map = {} # Used to correctly reassemble tool call arguments

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # If the chunk has text content, it's a direct answer. Stream it immediately.
                if delta.content:
                    # Yield a structured event for the frontend
                    yield {"type": "answer_chunk", "content": delta.content}
                    if response_message["content"] is not None:
                         response_message["content"] += delta.content

                # If the chunk has tool call data, reconstruct it.
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        index = tc_delta.index
                        if index not in tool_call_index_map:
                            tool_call_index_map[index] = {
                                "id": "", "type": "function", "function": {"name": "", "arguments": ""}
                            }
                        if tc_delta.id:
                            tool_call_index_map[index]["id"] += tc_delta.id
                        if tc_delta.function and tc_delta.function.name:
                            tool_call_index_map[index]["function"]["name"] += tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments:
                            tool_call_index_map[index]["function"]["arguments"] += tc_delta.function.arguments

            # Finalize the reconstructed tool calls
            if tool_call_index_map:
                response_message["tool_calls"] = list(tool_call_index_map.values())
            
            tool_calls = response_message["tool_calls"]

            # If there were no tool calls, the direct answer is complete. We can stop here.
            if not tool_calls:
                logging.info("   [Model responded directly without using a tool.]")
                return

            # --- If we reach here, the model wants to use one or more tools ---
            logging.info(f"   [Step 2: Model requested {len(tool_calls)} tool call(s). Executing them...]")
            messages.append(response_message) # Add the assistant's decision to call a tool to the history

            # === TOOL EXECUTION PHASE ===
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                
                # Yield a "thinking" event to the frontend BEFORE running the tool
                yield {"type": "tool_call", "tool_name": function_name}

                function_to_call = available_tools.get(function_name)
                if function_to_call:
                    try:
                        function_args = json.loads(tool_call["function"]["arguments"] or "{}")
                        
                        # CRITICAL: Inject session_meta for private/session-aware tools
                        # Add any other tool names here that require the session_meta object.
                        if function_name in ["get_user_order_profile_as_markdown"]:
                            function_args['session_meta'] = session_meta
                        
                        # Execute the tool function (sync or async)
                        if asyncio.iscoroutinefunction(function_to_call):
                            function_response = await function_to_call(**function_args)
                        else:
                            # Run synchronous tool functions in a separate thread
                            function_response = await asyncio.to_thread(function_to_call, **function_args)
                        
                        # Append the tool's result to the message history
                        messages.append({
                            "tool_call_id": tool_call["id"],
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_response),
                        })
                    except Exception as e:
                        logging.error(f"Error executing tool '{function_name}': {e}", exc_info=True)
                        messages.append({
                            "tool_call_id": tool_call["id"], "role": "tool", "name": function_name,
                            "content": f"Error: Tool execution failed with message: {e}"
                        })
                else:
                    logging.warning(f"Model tried to call an unknown tool: {function_name}")

            # === FINAL LLM CALL: Synthesize the final answer using the tool results ===
            logging.info("   [Step 3: Streaming final answer from model...]")
            final_stream = await self.client.chat.completions.create(
                model=self.model, messages=messages, stream=True, **kwargs
            )

            async for chunk in final_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    # Yield the final answer chunks in the correct event format
                    yield {"type": "answer_chunk", "content": chunk.choices[0].delta.content}

        except Exception as e:
            logging.error(f"An error occurred during the streaming tool invocation process: {e}", exc_info=True)
            # Yield a structured error event to the frontend
            yield {"type": "error", "content": "An internal error occurred while processing your request."}
        
async def main():
    # --- Pydantic Models for Testing ---
    class NIDInfo(BaseModel):
        name: str = Field(description="The person's full name in Bengali.")
        father_name: str = Field(description="The person's father's name in Bengali.")
        occupation: str = Field(description="The person's occupation in Bengali.")

    class PassportInfo(BaseModel):
        application_type: str = Field(description="The type of passport application, e.g., 'নতুন' (New) or 'নবায়ন' (Renewal).")
        delivery_type: str = Field(description="The delivery speed, e.g., 'জরুরি' (Urgent) or 'সাধারণ' (Regular).")
        validity_years: int = Field(description="The validity period of the passport in years.")
        
    # --- Setup and Initialization ---
    print("--- Running Asynchronous LLMService Tests ---")
    
    # Load Qwen LLM Config
    api_key = os.getenv("VLLM_API_KEY")
    model = os.getenv("VLLM_MODEL_NAME")
    base_url = os.getenv("VLLM_BASE_URL")
    llm_service = None
    if all([api_key, model, base_url]):
        llm_service = AsyncLLMService(api_key, model, base_url, max_context_tokens=32000)
    else:
        print("\nWARNING: Qwen LLM environment variables not set. Skipping tests.")
        return

    # --- Test Cases ---

    # Test 1: Invoke
    print("\n--- Test 1: Invoke (Async) ---")
    try:
        prompt = "জন্ম নিবন্ধন সনদের গুরুত্ব কী?"
        print(f"Prompt: {prompt}")
        response = await llm_service.invoke(prompt, temperature=0.1, max_tokens=256)
        print(f"Response:\n{response}")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Test 2: Stream
    print("\n--- Test 2: Stream (Async) ---")
    try:
        prompt = "পাসপোর্ট অফিসের একজন কর্মকর্তার একটি সংক্ষিপ্ত বর্ণনা দিন।"
        print(f"Prompt: {prompt}\nStreaming Response:")
        async for chunk in llm_service.stream(prompt, temperature=0.2, max_tokens=256):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"An error occurred: {e}")

    # Test 3: Structured Invoke
    print("\n--- Test 3: Structured Invoke (Async) ---")
    try:
        prompt = "আমার নাম 'করিম চৌধুরী', পিতার নাম 'রহিম চৌধুরী', আমি একজন ছাত্র। এই তথ্য দিয়ে একটি এনআইডি কার্ডের তথ্য তৈরি করুন।"
        print(f"Prompt: {prompt}")
        nid_data = await llm_service.invoke_structured(prompt, NIDInfo, temperature=0.0)
        print(f"Parsed Response:\n{nid_data.model_dump_json(indent=2)}")
    except Exception as e:
        print(f"An error occurred: {e}")
            
    # Test 4: Invoke with Tools (Time Tool Example)
    print("\n--- Test 4: Invoke with Tools - Time Tool Example (Async) ---")
    try:
        user_prompt = "এখন সময় কত?"
        print(f"Prompt: {user_prompt}")
        messages = [{"role": "user", "content": user_prompt}]
        final_response = await llm_service.invoke_with_tools(
            messages=messages, tools=tools_list, available_tools=available_tools_map, temperature=0.0
        )
        print(f"\nFinal Model Response:\n{final_response}")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Test 5: Stream with Tool Calls (Time Tool Example)
    print("\n--- Test 5: Stream with Tool Calls - Time Tool Example (Async) ---")
    try:
        user_prompt = "এখন সময় কত?"
        print(f"Prompt: {user_prompt}\nStreaming Response:")
        messages = [{"role": "user", "content": user_prompt}]
        async for chunk in llm_service.stream_with_tool_calls(
            messages=messages, tools=tools_list, available_tools=available_tools_map, temperature=0.0
        ):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"An error occurred: {e}")

    # Test 6: Invoke with Tools (Retriever Tool Example)
    print("\n--- Test 6: Invoke with Tools - Retriever Tool Example (Async) ---")
    try:
        user_prompt = "আমার এন আই ডি হারায়ে গেছে রাস্তায়, কি করব?"
        print(f"Prompt: {user_prompt}")
        messages = [{"role": "user", "content": user_prompt}]
        final_response = await llm_service.invoke_with_tools(
            messages=messages, tools=tools_list, available_tools=available_tools_map
        )
        print(f"\nFinal Model Response:\n{final_response}")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Test 7: Stream with Tool Calls (Retriever Tool Example)
    print("\n--- Test 7: Stream with Tool Calls - Retriever Tool Example (Async) ---")
    try:
        user_prompt = "THIS IS A GOVT SERVICE RELATED QUERY. MAKE SURE YOU ANSWER FROM KNOWLEDGEBASE. আমার এন আই ডি হারায়ে গেছে রাস্তায়, কি করব? "
        print(f"Prompt: {user_prompt}\nStreaming Response:")
        messages = [{"role": "user", "content": user_prompt}]
        async for chunk in llm_service.stream_with_tool_calls(
            messages=messages, tools=tools_list, available_tools=available_tools_map
        ):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"An error occurred: {e}")
            
    print("\n--- All Asynchronous Tests Concluded ---")

if __name__ == '__main__':
    asyncio.run(main())