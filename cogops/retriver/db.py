import sys
import pandas as pd
import numpy as np
from loguru import logger
import psycopg2
from psycopg2.extensions import register_adapter, AsIs

from sqlalchemy import (
    create_engine,
    select,
    insert,
    delete,
    update,
    Table,
    Column,
    Integer,
    String,
    Text,
    Date,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.postgresql import insert as pg_insert


# --- Numpy Datatype Adapters for psycopg2 ---
# Prevents errors when inserting numpy data types into PostgreSQL.
def addapt_numpy_float64(numpy_float64):
    return AsIs(numpy_float64)
def addapt_numpy_int64(numpy_int64):
    return AsIs(numpy_int64)

register_adapter(np.float64, addapt_numpy_float64)
register_adapter(np.int64, addapt_numpy_int64)


# --- Declarative Base for ORM Models ---
class Base(DeclarativeBase):
    """Base class required for SQLAlchemy ORM models."""
    pass


# --- Passages Table Schema Definition ---
class Passages(Base):
    """
    Defines the schema for the 'passages' table. This class is used by
    SQLAlchemy to map to the database table structure.
    """
    __tablename__ = "passages"
    passage_id = Column(Integer, nullable=False, primary_key=True)
    topic = Column(String)
    text = Column(Text, nullable=False)
    date = Column(Date)

    def __repr__(self) -> str:
        return f"Passages(passage_id={self.passage_id!r}, topic={self.topic!r})"


# --- Database Management Class ---
class SQLDatabaseManager():
    """
    Manages the connection and CRUD operations for the 'passages' table
    in an existing PostgreSQL database.
    """
    def __init__(self, database_config: dict) -> None:
        """
        Initializes the database manager and connects to the database.

        Args:
            database_config (dict): Connection parameters (user, password, host, port, database).
        """
        self.config = database_config
        self.engine = self._create_engine()
        self.passages_table = Passages.__table__

    def _create_engine(self):
        """Creates and returns a SQLAlchemy engine."""
        try:
            conn_url = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'.format(**self.config)
            return create_engine(conn_url, echo=self.config.get('echo', False))
        except Exception as exc:
            logger.error(f"Could not create database engine: {exc}")
            sys.exit(-1)

    def insert_passages(self, insert_data: list[dict]) -> int:
        """Inserts new rows into the passages table."""
        if not insert_data:
            return 0
        try:
            with self.engine.connect() as conn:
                conn.execute(insert(self.passages_table), insert_data)
                conn.commit()
            logger.info(f"Successfully inserted {len(insert_data)} passages.")
            return 0
        except Exception as exc:
            logger.error(f"An error occurred during INSERT: {exc}")
            sys.exit(-1)

    def select_passages(self, condition_dict: dict = None) -> pd.DataFrame:
        """Selects rows from the passages table based on conditions."""
        stmt = select(self.passages_table)
        if condition_dict:
            stmt = stmt.where(*[
                getattr(self.passages_table.c, col) == val for col, val in condition_dict.items()
            ])
        try:
            with self.engine.connect() as conn:
                return pd.read_sql(stmt, conn)
        except Exception as exc:
            logger.error(f"An error occurred during SELECT: {exc}")
            sys.exit(-1)
            
    def select_passages_by_ids(self, passage_ids: list) -> pd.DataFrame:
        """Selects passages from the table by a list of passage_ids."""
        if not passage_ids:
            return pd.DataFrame()
        stmt = select(self.passages_table).where(self.passages_table.c.passage_id.in_(passage_ids))
        try:
            with self.engine.connect() as conn:
                return pd.read_sql(stmt, conn)
        except Exception as exc:
            logger.error(f"An error occurred during SELECT_BY_IDS: {exc}")
            sys.exit(-1)

    def update_passages(self, condition_columns: list, update_array: list[dict]) -> int:
        """Updates existing rows in the passages table."""
        if not update_array:
            return 0
        try:
            with self.engine.connect() as conn:
                for item in update_array:
                    conditions = {col: item[col] for col in condition_columns}
                    values = {k: v for k, v in item.items() if k not in condition_columns}
                    stmt = update(self.passages_table).where(
                        *[getattr(self.passages_table.c, col) == val for col, val in conditions.items()]
                    ).values(values)
                    conn.execute(stmt)
                conn.commit()
            logger.info(f"Successfully processed {len(update_array)} update operations.")
            return 0
        except Exception as exc:
            logger.error(f"An error occurred during UPDATE: {exc}")
            sys.exit(-1)

    def upsert_passages(self, insert_data: list[dict], update_columns: list[str]) -> int:
        """Inserts new passages or updates them on primary key conflict (PostgreSQL specific)."""
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
            logger.error(f"An error occurred during UPSERT: {exc}")
            sys.exit(-1)

    def delete_passages(self, condition_dict: dict) -> int:
        """Deletes rows from the passages table based on conditions."""
        if not condition_dict:
            logger.error("DELETE operation requires conditions but none were provided.")
            return -1
        stmt = delete(self.passages_table).where(*[
            getattr(self.passages_table.c, col) == val for col, val in condition_dict.items()
        ])
        try:
            with self.engine.connect() as conn:
                result = conn.execute(stmt)
                conn.commit()
            logger.info(f"DELETE operation affected {result.rowcount} rows.")
            return 0
        except Exception as exc:
            logger.error(f"An error occurred during DELETE: {exc}")
            sys.exit(-1)