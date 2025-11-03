# --- START OF FINAL CORRECTED FILE: cogops/utils/redis_manager.py ---

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool

# --- Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SESSION_TTL_SECONDS = 48 * 60 * 60  # 48 hours
HISTORY_MAX_LENGTH = 20  # Keep the last 10 user/assistant pairs

class RedisManager:
    """
    A singleton-like class to manage a single, application-wide Redis connection pool.
    This centralized manager handles all interactions with Redis for session data
    and conversation history, ensuring consistency and efficient connection management.
    """
    _pool: Optional[ConnectionPool] = None

    @classmethod
    def _get_pool(cls) -> ConnectionPool:
        """Initializes or returns the existing Redis connection pool."""
        if cls._pool is None:
            logging.info(f"Initializing Redis connection pool at {REDIS_HOST}:{REDIS_PORT}...")
            cls._pool = ConnectionPool(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,
                decode_responses=True,
                max_connections=50
            )
            logging.info("✅ Redis connection pool initialized.")
        return cls._pool

    @classmethod
    def get_client(cls) -> aioredis.Redis:
        """Provides a Redis client instance from the shared connection pool."""
        return aioredis.Redis(connection_pool=cls._get_pool())

    @classmethod
    async def create_session(cls, session_id: str, session_meta: Dict[str, Any]) -> None:
        """
        Creates a new session hash in Redis, sanitizing input to prevent errors.
        """
        client = cls.get_client()

        # --- CRITICAL FIX: Sanitize the mapping to prevent DataError. ---
        # REASON: The redis client cannot serialize 'None'. We MUST convert any
        # None values to a storable format (like an empty string) before writing.
        # This makes the manager robust to the frontend sending None values.
        sanitized_meta = {
            str(k): (str(v) if v is not None else "") for k, v in session_meta.items()
        }

        async with client.pipeline() as pipe:
            await pipe.hset(f"session:{session_id}", mapping=sanitized_meta)
            await pipe.expire(f"session:{session_id}", SESSION_TTL_SECONDS)
            await pipe.execute()
        logging.info(f"Created new Redis session: {session_id}")

    @classmethod
    async def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a session hash from Redis."""
        client = cls.get_client()
        return await client.hgetall(f"session:{session_id}")

    @classmethod
    async def append_to_history(cls, session_id: str, user_message: str, assistant_message: str) -> None:
        """Appends a conversation turn to the Redis history list."""
        client = cls.get_client()
        user_turn = json.dumps({"role": "user", "content": user_message})
        assistant_turn = json.dumps({"role": "assistant", "content": assistant_message})

        async with client.pipeline() as pipe:
            await pipe.lpush(f"history:{session_id}", assistant_turn, user_turn)
            await pipe.ltrim(f"history:{session_id}", 0, HISTORY_MAX_LENGTH - 1)
            await pipe.expire(f"history:{session_id}", SESSION_TTL_SECONDS)
            await pipe.execute()

    @classmethod
    async def get_history(cls, session_id: str) -> List[Tuple[str, str]]:
        """Retrieves and reconstructs recent conversation history from Redis."""
        client = cls.get_client()
        history_json = await client.lrange(f"history:{session_id}", 0, -1)
        if not history_json:
            return []

        history_json.reverse()
        history = []
        for i in range(0, len(history_json), 2):
            try:
                user_turn = json.loads(history_json[i])
                if i + 1 < len(history_json):
                    assistant_turn = json.loads(history_json[i+1])
                    if user_turn['role'] == 'user' and assistant_turn['role'] == 'assistant':
                        history.append((user_turn['content'], assistant_turn['content']))
            except (json.JSONDecodeError, KeyError) as e:
                logging.warning(f"Could not parse history item for session {session_id}: {e}")
        return history

    @classmethod
    async def delete_session(cls, session_id: str) -> None:
        """Deletes all Redis keys for a given session."""
        client = cls.get_client()
        await client.delete(f"session:{session_id}", f"history:{session_id}")
        logging.info(f"Deleted Redis data for session: {session_id}")

    @classmethod
    async def close_pool(cls) -> None:
        """Closes the Redis connection pool on application shutdown."""
        if cls._pool:
            logging.info("Closing Redis connection pool.")
            await cls._pool.disconnect()
            cls._pool = None

# Create a single instance for the application to use.
redis_manager = RedisManager()

# --- END OF FINAL CORRECTED FILE: cogops/utils/redis_manager.py ---