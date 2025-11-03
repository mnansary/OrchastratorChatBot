# --- START OF FINAL CORRECTED FILE: cogops/tasks/cleanup.py ---

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from cogops.retriver.db import Sessions, ConversationHistory
# NOTE: redis_manager is not needed here as we are now only handling PostgreSQL cleanup.
# Redis keys are deleted immediately on /clear_session and have their own TTL.

PURGE_GRACE_PERIOD_MINUTES = 60

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# CRITICAL FIX: The function is now SYNCHRONOUS.
# REASON: All SQLAlchemy session operations within are blocking.
# This function is intended to be run in a separate thread to avoid blocking the main async loop.
def purge_deleted_sessions_sync(db: Session):
    """
    Finds and permanently deletes session data from PostgreSQL for sessions
    that were soft-deleted more than the grace period ago.
    """
    logging.info("Starting synchronous cleanup task: Purging old soft-deleted sessions...")

    # Calculate the cutoff time for purging.
    cutoff_time = datetime.utcnow() - timedelta(minutes=PURGE_GRACE_PERIOD_MINUTES)

    try:
        # 1. Find all session IDs that are ready to be purged from PostgreSQL.
        stmt = select(Sessions.session_id).where(
            Sessions.deleted_at != None,
            Sessions.deleted_at < cutoff_time
        )
        sessions_to_purge = db.execute(stmt).scalars().all()

        if not sessions_to_purge:
            logging.info("Cleanup task finished: No sessions to purge.")
            return

        logging.info(f"Found {len(sessions_to_purge)} sessions to permanently delete.")

        # 2. Delete the data from PostgreSQL in a single transaction.
        # This is more efficient than deleting one by one.

        # Delete from the 'conversation_history' table first due to the foreign key constraint.
        history_delete_stmt = delete(ConversationHistory).where(ConversationHistory.session_id.in_(sessions_to_purge))
        history_result = db.execute(history_delete_stmt)

        # Then, delete from the 'sessions' table.
        session_delete_stmt = delete(Sessions).where(Sessions.session_id.in_(sessions_to_purge))
        session_result = db.execute(session_delete_stmt)
        
        db.commit()
        logging.info(f"Purged {history_result.rowcount} history records and {session_result.rowcount} session records from PostgreSQL.")

    except Exception as e:
        logging.error(f"Failed to purge sessions from PostgreSQL: {e}", exc_info=True)
        db.rollback() # Roll back the transaction on failure.

    logging.info("✅ Synchronous cleanup task finished.")


# --- END OF FINAL CORRECTED FILE: cogops/tasks/cleanup.py ---