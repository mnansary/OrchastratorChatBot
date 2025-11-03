# --- START OF FINAL CORRECTED FILE: api_service.py ---

import asyncio
import json
import uvicorn
import uuid
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

# --- Core Application Components ---
from cogops.agent import ChatAgent
from cogops.context_manager import context_manager
from cogops.utils.redis_manager import redis_manager
from cogops.utils.db_config import get_postgres_config
from sqlalchemy import create_engine, insert, update, select
from sqlalchemy.orm import sessionmaker, Session
from cogops.retriver.db import Sessions, ConversationHistory
from datetime import datetime

# CRITICAL FIX: Import the correct synchronous cleanup function.
from cogops.tasks.cleanup import purge_deleted_sessions_sync

# --- Global Configuration ---
AGENT_CONFIG_PATH = "configs/config.yaml"
DEFAULT_STORE_ID = 37
GUEST_CUSTOMER_ID = "369"
CLEANUP_INTERVAL_SECONDS = 3600  # Run every 1 hour

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

chat_agent: Optional[ChatAgent] = None
db_config = get_postgres_config()
engine = create_engine(f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(
    title="Bengal Meat Chat Agent API",
    description="A stateless, session-based API for the Bengal Meat Chat Agent.",
    version="4.1.0", # Final Version
)

# CRITICAL FIX: The scheduler now runs the synchronous DB task in a separate thread.
# REASON: This prevents blocking the main application's async event loop, which is a critical performance issue.
async def run_cleanup_scheduler():
    """
    A simple asyncio-based scheduler that runs the synchronous purge task
    in a separate thread at a regular interval.
    """
    logging.info(f"Cleanup scheduler started. Will run every {CLEANUP_INTERVAL_SECONDS} seconds.")
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            with SessionLocal() as db:
                # Run the blocking function in a thread pool to avoid blocking the event loop.
                await asyncio.to_thread(purge_deleted_sessions_sync, db)
        except Exception as e:
            logging.error(f"An error occurred in the cleanup scheduler: {e}", exc_info=True)

@app.on_event("startup")
async def startup_event():
    """
    On application startup:
    1. Build static context.
    2. Initialize the ChatAgent singleton.
    3. Start the background cleanup scheduler.
    """
    global chat_agent
    logging.info("Application startup: Building static context...")
    context_manager.build_static_context(store_id=DEFAULT_STORE_ID, customer_id=GUEST_CUSTOMER_ID)
    logging.info("Initializing stateless ChatAgent singleton...")
    chat_agent = ChatAgent(config_path=AGENT_CONFIG_PATH)
    
    # Launch the scheduler as a background task.
    asyncio.create_task(run_cleanup_scheduler())
    
    logging.info("✅ Application is ready to accept requests.")

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Application shutdown: Closing connections...")
    await redis_manager.close_pool()
    logging.info("✅ Connections closed.")

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    session_meta: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    query: Optional[str] = None

class ClearSessionRequest(BaseModel):
    session_id: str

class HistoryMessage(BaseModel):
    role: str
    content: str
    created_at: datetime

class HistoryResponse(BaseModel):
    session_id: str
    history: List[HistoryMessage]

# --- Database Dependency & Helpers ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_new_session_to_db(session_id: str, session_meta: Dict[str, Any]):
    with SessionLocal() as db:
        stmt = insert(Sessions).values(
            session_id=session_id, user_id=session_meta.get('user_id'), store_id=session_meta.get('store_id')
        )
        db.execute(stmt)
        db.commit()
    logging.info(f"Logged new session to PostgreSQL: {session_id}")

def log_conversation_turn_to_db(session_id: str, user_query: str, assistant_response: str):
    with SessionLocal() as db:
        user_stmt = insert(ConversationHistory).values(
            session_id=session_id, role='user', content=user_query
        )
        assistant_stmt = insert(ConversationHistory).values(
            session_id=session_id, role='assistant', content=assistant_response
        )
        db.execute(user_stmt)
        db.execute(assistant_stmt)
        db.commit()

def mark_session_deleted_in_db(session_id: str):
    with SessionLocal() as db:
        stmt = update(Sessions).where(Sessions.session_id == session_id).values(deleted_at=datetime.utcnow())
        db.execute(stmt)
        db.commit()

# --- API Endpoints ---
@app.get("/health", tags=["Monitoring"])
async def health_check():
    return {"status": "ok"}

@app.get("/chat/history/{session_id}", response_model=HistoryResponse, tags=["Session Management"])
async def get_chat_history(session_id: str, db: Session = Depends(get_db)):
    session_record = db.query(Sessions).filter(Sessions.session_id == session_id, Sessions.deleted_at == None).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Session not found or has been deleted.")
    history_records = db.query(ConversationHistory).filter(ConversationHistory.session_id == session_id).order_by(ConversationHistory.created_at.asc()).all()
    return HistoryResponse(
        session_id=session_id,
        history=[
            HistoryMessage(role=record.role, content=record.content, created_at=record.created_at) for record in history_records
        ]
    )

@app.post("/chat/clear_session", tags=["Session Management"])
async def clear_session(request: ClearSessionRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id
    # Immediate deletion from Redis for responsiveness.
    await redis_manager.delete_session(session_id)
    # Background task to soft-delete from PostgreSQL.
    background_tasks.add_task(mark_session_deleted_in_db, session_id)
    logging.info(f"-> Cleared session for session_id: {session_id}")
    return {"status": "success", "message": f"Session '{session_id}' has been cleared."}

@app.post("/chat/stream", tags=["Chat"])
async def stream_chat(chat_request: ChatRequest, background_tasks: BackgroundTasks):
    async def response_generator():
        if chat_request.session_meta and not chat_request.session_id:
            if 'store_id' not in chat_request.session_meta:
                yield f'{json.dumps({"type": "error", "content": "FATAL: store_id is missing."})}\n'
                return
            new_session_id = str(uuid.uuid4())
            await redis_manager.create_session(new_session_id, chat_request.session_meta)
            background_tasks.add_task(log_new_session_to_db, new_session_id, chat_request.session_meta)
            yield f'{json.dumps({"type": "session_id", "id": new_session_id})}\n'
            async for event in chat_agent.generate_welcome_message(chat_request.session_meta):
                yield f"{json.dumps(event, ensure_ascii=False)}\n"
            return
        elif chat_request.session_id:
            if not chat_request.query:
                yield f'{json.dumps({"type": "error", "content": "Query is missing."})}\n'
                return
            session_id = chat_request.session_id
            session_meta = await redis_manager.get_session(session_id)
            if not session_meta:
                yield f'{json.dumps({"type": "error", "content": f"Invalid session_id: {session_id}"})}\n'
                return
            history = await redis_manager.get_history(session_id)
            user_context = await chat_agent.generate_user_context(session_meta)
            full_assistant_response = []
            stream = chat_agent.process_query(
                user_query=chat_request.query, session_meta=session_meta, history=history,
                location_context=context_manager.location_context, store_catalog=context_manager.store_catalog,
                user_context=user_context
            )
            async for event in stream:
                if event.get("type") == "answer_chunk":
                    full_assistant_response.append(event.get("content", ""))
                yield f"{json.dumps(event, ensure_ascii=False)}\n"
            final_response_str = "".join(full_assistant_response).strip()
            if final_response_str:
                await redis_manager.append_to_history(session_id, chat_request.query, final_response_str)
                background_tasks.add_task(log_conversation_turn_to_db, session_id, chat_request.query, final_response_str)
            return
        else:
            yield f'{json.dumps({"type": "error", "content": "Invalid request."})}\n'
    return StreamingResponse(response_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    uvicorn.run("api_service:app", host="0.0.0.0", port=9000, reload=True)

# --- END OF FINAL CORRECTED FILE: api_service.py ---