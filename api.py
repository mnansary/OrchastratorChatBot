# FILE: api_service.py

import asyncio
import json
import uvicorn
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
from cogops.agent import ChatAgent
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# --- Global Configuration ---
AGENT_CONFIG_PATH = "configs/config.yaml"

# --- API Setup ---
app = FastAPI(
    title="Bengal Meat Chat Agent API",
    description="A session-based API for the Bengal Meat Chat Agent service.",
    version="3.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- Session Management ---
# This dictionary now maps a unique session_id (UUID) to a ChatAgent instance.
chat_sessions: Dict[str, ChatAgent] = {}
sessions_lock = asyncio.Lock()

# --- Pydantic Models for a Unified Request Body ---
class ChatRequest(BaseModel):
    session_meta: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    query: Optional[str] = None # Query is optional only for the very first call

# --- API Endpoints ---
@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Confirms the service is running and reports the number of active sessions."""
    return {"status": "ok", "active_sessions": len(chat_sessions)}

@app.post("/chat/clear_session", tags=["Session Management"])
async def clear_session(request: Dict[str, str]):
    """Clears conversation history by deleting the session instance."""
    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
        
    async with sessions_lock:
        if session_id in chat_sessions:
            del chat_sessions[session_id]
            message = f"Session '{session_id}' has been cleared."
        else:
            message = f"No active session found for session_id '{session_id}'."
            
    return {"status": "success", "message": message}

@app.post("/chat/stream", tags=["Chat"])
async def stream_chat(chat_request: ChatRequest):
    """
    Main chat endpoint with session management.
    - On the first call, expects 'session_meta'. Creates a session, returns a 'session_id', and a welcome message.
    - On subsequent calls, expects 'session_id' and a 'query' to continue the conversation.
    """
    async def response_generator():
        # --- Case 1: Initial Request (Create New Session) ---
        if chat_request.session_meta and not chat_request.session_id:
            if 'store_id' not in chat_request.session_meta:
                yield f'{json.dumps({"type": "error", "content": "store_id is missing from session_meta."})}\n'
                return

            new_session_id = str(uuid.uuid4())
            logging.info(f"-> Creating new session {new_session_id} with meta: {chat_request.session_meta}")
            
            async with sessions_lock:
                # Instantiate the agent with the session metadata
                session = ChatAgent(config_path=AGENT_CONFIG_PATH, session_meta=chat_request.session_meta)
                chat_sessions[new_session_id] = session
            
            # The VERY FIRST message must be the new session_id for the frontend
            yield f'{json.dumps({"type": "session_id", "id": new_session_id})}\n'
            
            # Now, stream the welcome message
            async for event in session.generate_welcome_message():
                yield f"{json.dumps(event, ensure_ascii=False)}\n"

        # --- Case 2: Subsequent Request (Continue Existing Session) ---
        elif chat_request.session_id:
            if not chat_request.query:
                yield f'{json.dumps({"type": "error", "content": "query is missing for an existing session."})}\n'
                return

            async with sessions_lock:
                session = chat_sessions.get(chat_request.session_id)

            if not session:
                yield f'{json.dumps({"type": "error", "content": f"Invalid or expired session_id: {chat_request.session_id}"})}\n'
                return
            
            # Process the user's query and stream the response
            async for event in session.process_query(chat_request.query):
                yield f"{json.dumps(event, ensure_ascii=False)}\n"
        
        # --- Case 3: Invalid Request ---
        else:
            yield f'{json.dumps({"type": "error", "content": "Invalid request. Provide either session_meta (for new session) or session_id (for existing session)."})}\n'
    
    return StreamingResponse(response_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    uvicorn.run("api_service:app", host="0.0.0.0", port=9000, reload=True)