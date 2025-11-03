# --- START OF NEW FILE: test_integration.py ---

import pytest
import httpx
import asyncio
import uuid
import json
import os
import redis.asyncio as aioredis

# --- Configuration ---
# This assumes your API is running on the default host and port.
API_BASE_URL = "http://127.0.0.1:9000"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
DEFAULT_SESSION_META = {
    "store_id": 37, # Using the default from your config
    "user_id": None,
    "access_token": None,
    "refresh_token": None
}

# This marks all tests in this file to be run with asyncio.
pytestmark = pytest.mark.asyncio


# --- Helper Fixture for HTTP Client ---
@pytest.fixture(scope="function") # CRITICAL FIX: Changed from "module" to "function"
async def async_client():
    """
    Provides a shared async HTTP client for all tests in this module.
    REASON FOR CHANGE: pytest-asyncio in auto mode creates a new event loop
    per test function. A module-scoped fixture's event loop would be closed
    after the first test, causing subsequent tests to fail. Function scope
    ensures a fresh client is created for each test's new event loop.
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30) as client:
        yield client
# --- Test Cases ---

async def test_health_check(async_client: httpx.AsyncClient):
    """
    PURPOSE: To confirm the API server is running and responsive.
    ACTION: Makes a GET request to the /health endpoint.
    ASSERTION: Expects a 200 OK status and a JSON body with "status": "ok".
    """
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_guest_session(async_client: httpx.AsyncClient):
    """
    PURPOSE: To verify the creation of a new guest session.
    ACTION: Makes a POST request to /chat/stream with session_meta.
    ASSERTION:
        1. The response is 200 OK.
        2. The first event in the stream is a 'session_id' event.
        3. The session_id is a valid UUID string.
        4. Subsequent events are 'welcome_message' chunks.
    """
    payload = {"session_meta": DEFAULT_SESSION_META}
    
    session_id_received = None
    welcome_message_received = False
    
    async with async_client.stream("POST", "/chat/stream", json=payload) as response:
        assert response.status_code == 200
        
        async for line in response.aiter_lines():
            event = json.loads(line)
            
            if event["type"] == "session_id":
                session_id_received = event["id"]
                # Assert that the ID looks like a UUID.
                assert uuid.UUID(session_id_received, version=4)
            
            elif event["type"] == "welcome_message":
                welcome_message_received = True
                assert "content" in event
    
    assert session_id_received is not None, "Did not receive a session_id event."
    assert welcome_message_received is True, "Did not receive a welcome_message event."


async def test_chat_and_history_persistence(async_client: httpx.AsyncClient):
    """
    PURPOSE: To verify that a chat message is processed and the turn is
             persisted correctly in PostgreSQL.
    ACTION:
        1. Create a new guest session.
        2. Send a query to the /chat/stream endpoint using the new session_id.
        3. Fetch the history from the /chat/history/{session_id} endpoint.
    ASSERTION:
        1. The chat stream returns answer chunks.
        2. The history endpoint returns a 200 OK.
        3. The fetched history contains exactly two entries (user and assistant).
        4. The content of the user entry matches the query sent.
    """
    # 1. Create a session
    create_payload = {"session_meta": DEFAULT_SESSION_META}
    session_id = None
    async with async_client.stream("POST", "/chat/stream", json=create_payload) as r:
        first_line = await r.aiter_lines().__anext__()
        session_id = json.loads(first_line)["id"]

    assert session_id is not None

    # 2. Send a query
    query_text = "Hello, this is a test query."
    chat_payload = {"session_id": session_id, "query": query_text}
    
    async with async_client.stream("POST", "/chat/stream", json=chat_payload) as response:
        assert response.status_code == 200
        # Consume the stream to ensure the background tasks for logging are triggered
        async for _ in response.aiter_lines():
            pass

    # Give a moment for the background task to complete the DB write.
    await asyncio.sleep(1)

    # 3. Fetch history from PostgreSQL via the API
    history_response = await async_client.get(f"/chat/history/{session_id}")
    assert history_response.status_code == 200
    
    history_data = history_response.json()
    assert history_data["session_id"] == session_id
    
    history_list = history_data["history"]
    assert len(history_list) == 2, "History should contain exactly one user and one assistant message."
    
    assert history_list[0]["role"] == "user"
    assert history_list[0]["content"] == query_text
    assert history_list[1]["role"] == "assistant"


async def test_clear_session_cascade(async_client: httpx.AsyncClient):
    """
    PURPOSE: To verify the end-to-end deletion cascade.
    ACTION:
        1. Create a new session and send a message (to populate all data stores).
        2. Call the /chat/clear_session endpoint.
        3. Attempt to fetch the history for the deleted session.
        4. Directly check Redis to confirm keys are gone.
    ASSERTION:
        1. The clear_session call is successful (200 OK).
        2. The subsequent attempt to fetch history results in a 404 Not Found.
        3. The session and history keys are no longer present in Redis.
    """
    # 1. Create a session and some data
    create_payload = {"session_meta": DEFAULT_SESSION_META}
    session_id = None
    async with async_client.stream("POST", "/chat/stream", json=create_payload) as r:
        first_line = await r.aiter_lines().__anext__()
        session_id = json.loads(first_line)["id"]

    chat_payload = {"session_id": session_id, "query": "This session will be deleted."}
    async with async_client.stream("POST", "/chat/stream", json=chat_payload) as r:
        async for _ in r.aiter_lines(): pass

    # 2. Call clear_session
    clear_payload = {"session_id": session_id}
    clear_response = await async_client.post("/chat/clear_session", json=clear_payload)
    assert clear_response.status_code == 200

    # 3. Verify soft deletion by checking the history endpoint
    history_response = await async_client.get(f"/chat/history/{session_id}")
    assert history_response.status_code == 404, "API should return 404 for a cleared session."

    # 4. Hardcore Verification: Directly check Redis
    redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    session_key_exists = await redis_client.exists(f"session:{session_id}")
    history_key_exists = await redis_client.exists(f"history:{session_id}")
    await redis_client.close()

    assert session_key_exists == 0, "Session key should be deleted from Redis."
    assert history_key_exists == 0, "History key should be deleted from Redis."

# --- END OF NEW FILE: test_integration.py ---