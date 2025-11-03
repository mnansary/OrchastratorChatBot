# --- START OF MODIFIED FILE: cogops/retriver/db.py ---

import sys
import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger
from typing import List, Dict

import psycopg2
from psycopg2.extensions import register_adapter, AsIs

from sqlalchemy import (
    create_engine,
    select,
    insert,
    delete,
    update,
    Text,
    Date,
    String,
    Integer,
    ForeignKey,
    DateTime,
    func
)
from sqlalchemy.dialects.postgresql import insert as pg_insert, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# --- Numpy Datatype Adapters for psycopg2 ---
# Prevents errors when inserting numpy data types into PostgreSQL.
def addapt_numpy_float64(numpy_float64):
    return AsIs(numpy_float64)
def addapt_numpy_int64(numpy_int64):
    return AsIs(numpy_int64)

register_adapter(np.float64, addapt_numpy_float64)
register_adapter(np.int64, addapt_numpy_int64)


# --- ORM Declarative Base ---
# All of our table models will inherit from this class.
class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""
    pass


# --- Passages Table Schema Definition (Existing) ---
class Passages(Base):
    """
    Defines the schema for the 'passages' table, which stores the RAG knowledge base.
    """
    __tablename__ = "passages"
    passage_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=True)

    def __repr__(self) -> str:
        return f"Passages(passage_id={self.passage_id!r}, topic={self.topic!r})"


# --- Sessions Table Schema Definition (NEW) ---
class Sessions(Base):
    """
    NEW: Defines the schema for the 'sessions' table.
    REASON: Provides a permanent record of every chat session, including user
    and store context, and tracking creation/deletion times for analytics.
    """
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=True)
    store_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Establishes a one-to-many relationship with ConversationHistory
    history: Mapped[List["ConversationHistory"]] = relationship(back_populates="session")

    def __repr__(self) -> str:
        return f"Sessions(session_id={self.session_id!r}, user_id={self.user_id!r})"


# --- Conversation History Table Schema Definition (NEW) ---
class ConversationHistory(Base):
    """
    NEW: Defines the schema for the 'conversation_history' table.
    REASON: This is the permanent, append-only log of every message exchanged.
    It is the backbone for the history retrieval API and for auditing.
    """
    __tablename__ = "conversation_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sessions.session_id"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Establishes a many-to-one relationship with Sessions
    session: Mapped["Sessions"] = relationship(back_populates="history")

    def __repr__(self) -> str:
        return f"ConversationHistory(id={self.id!r}, session_id={self.session_id!r}, role={self.role!r})"


# --- Database Management Class ---
class SQLDatabaseManager():
    """
    Manages the connection and CRUD operations for all tables
    in the PostgreSQL database.
    """
    def __init__(self, database_config: dict) -> None:
        """Initializes the database manager and connects to the database."""
        self.config = database_config
        self.engine = self._create_engine()
        # Keep a reference to the table objects for convenience
        self.passages_table = Passages.__table__
        self.sessions_table = Sessions.__table__
        self.history_table = ConversationHistory.__table__

    def _create_engine(self):
        """Creates and returns a SQLAlchemy engine."""
        try:
            conn_url = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'.format(**self.config)
            return create_engine(conn_url, echo=self.config.get('echo', False))
        except Exception as exc:
            logger.error(f"Could not create database engine: {exc}")
            sys.exit(-1)

    # --- Methods for 'passages' table ---
    def upsert_passages(self, insert_data: List[Dict], update_columns: List[str]) -> int:
        """Inserts new passages or updates them on primary key conflict."""
        if not insert_data:
            return 0
        try:
            pk = [key.name for key in self.passages_table.primary_key]
            stmt = pg_insert(self.passages_table).values(insert_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=pk,
                set_={col: getattr(stmt.excluded, col) for col in update_columns}
            )
            with self.engine.connect() as conn:
                conn.execute(stmt)
                conn.commit()
            logger.info(f"Successfully upserted {len(insert_data)} passages.")
            return 0
        except Exception as exc:
            logger.error(f"An error occurred during UPSERT into passages: {exc}")
            sys.exit(-1)

    def select_passages_by_ids(self, passage_ids: List[int]) -> pd.DataFrame:
        """Selects passages from the table by a list of passage_ids."""
        if not passage_ids:
            return pd.DataFrame()
        stmt = select(self.passages_table).where(self.passages_table.c.passage_id.in_(passage_ids))
        try:
            with self.engine.connect() as conn:
                return pd.read_sql(stmt, conn)
        except Exception as exc:
            logger.error(f"An error occurred during SELECT_BY_IDS from passages: {exc}")
            sys.exit(-1)

    # NOTE: Other methods like insert, update, delete for passages can remain if needed.

# --- END OF MODIFIED FILE: cogops/retriver/db.py ---