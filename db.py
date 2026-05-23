"""SQLite database helpers for the EUC Governance MVP."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from schema import CREATE_TABLES_SQL, DB_PATH, INDEX_SQL, UPLOAD_DIR

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / DB_PATH
UPLOAD_PATH = BASE_DIR / UPLOAD_DIR


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def to_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str, ensure_ascii=False)


@contextmanager
def get_connection() -> Iterable[sqlite3.Connection]:
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create database objects. Safe to run repeatedly."""
    with get_connection() as conn:
        for stmt in CREATE_TABLES_SQL:
            conn.execute(stmt)
        for stmt in INDEX_SQL:
            conn.execute(stmt)
        _apply_lightweight_migrations(conn)


def _apply_lightweight_migrations(conn: sqlite3.Connection) -> None:
    """Add MVP columns when a previous local DB already exists."""
    expected_columns = {
        "eucs": {
            "industrialization_rationale": "TEXT",
            "decommissioning_rationale": "TEXT",
            "mapping_na_justification": "TEXT",
        },
        "documents": {"deficiency_tag": "TEXT"},
        "exceptions": {"closure_evidence_document_id": "INTEGER"},
    }
    for table, columns in expected_columns.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, column_type in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    with get_connection() as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid or 0)


def execute_many(sql: str, rows: list[tuple[Any, ...]]) -> None:
    with get_connection() as conn:
        conn.executemany(sql, rows)


def dataframe(sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def table_count(table_name: str) -> int:
    row = fetch_one(f"SELECT COUNT(*) AS n FROM {table_name}")
    return int(row["n"] if row else 0)


def insert_audit(
    entity_type: str,
    entity_id: str | int,
    action: str,
    performed_by: str,
    old_value: Any = None,
    new_value: Any = None,
) -> None:
    execute(
        """
        INSERT INTO audit_trail(entity_type, entity_id, action, old_value, new_value, performed_by, performed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            str(entity_id),
            action,
            to_json(old_value) if old_value is not None else None,
            to_json(new_value) if new_value is not None else None,
            performed_by,
            utc_now(),
        ),
    )
