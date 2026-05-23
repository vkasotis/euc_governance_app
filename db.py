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
    """Create database objects and migrate older local databases safely.

    Streamlit Cloud preserves the SQLite file between source deployments. When
    a new release adds columns to a table that already exists, SQLite does not
    apply those additions from CREATE TABLE IF NOT EXISTS. Lightweight
    migrations therefore have to run before index creation and before any
    reference-data seeding.
    """
    with get_connection() as conn:
        for stmt in CREATE_TABLES_SQL:
            conn.execute(stmt)
        _apply_lightweight_migrations(conn)
        for stmt in INDEX_SQL:
            conn.execute(stmt)


def _apply_lightweight_migrations(conn: sqlite3.Connection) -> None:
    """Add MVP columns when a previous local DB already exists."""
    expected_columns = {
        "eucs": {
            "industrialization_rationale": "TEXT",
            "decommissioning_rationale": "TEXT",
            "mapping_na_justification": "TEXT",
        },
        "documents": {
            "deficiency_tag": "TEXT",
            "evidence_group_id": "TEXT",
        },
        "exceptions": {"closure_evidence_document_id": "INTEGER"},
        "user_profiles": {
            "username": "TEXT",
            "full_name": "TEXT",
            "email": "TEXT",
            "role": "TEXT",
            "active_flag": "INTEGER DEFAULT 1",
            "maker_checker_comments": "TEXT",
            "created_by": "TEXT",
            "created_at": "TEXT",
            "updated_by": "TEXT",
            "updated_at": "TEXT",
        },
        "raci_rules": {
            "activity_decision": "TEXT",
            "event_type": "TEXT",
            "euc_owner_raci": "TEXT",
            "data_validation_unit_raci": "TEXT",
            "gcc_raci": "TEXT",
            "group_it_governance_raci": "TEXT",
            "iof_raci": "TEXT",
            "data_governance_raci": "TEXT",
            "internal_audit_raci": "TEXT",
            "grm_strategy_raci": "TEXT",
            "active_flag": "INTEGER DEFAULT 1",
            "maker_checker_comments": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "notification_outbox": {
            "event_type": "TEXT",
            "activity_decision": "TEXT",
            "entity_type": "TEXT",
            "entity_id": "TEXT",
            "euc_id": "INTEGER",
            "reference_id": "TEXT",
            "subject": "TEXT",
            "body": "TEXT",
            "recipient_username": "TEXT",
            "recipient_email": "TEXT",
            "recipient_role": "TEXT",
            "raci_party": "TEXT",
            "raci_responsibility": "TEXT",
            "status": "TEXT DEFAULT 'Pending'",
            "created_by": "TEXT",
            "created_at": "TEXT",
            "sent_at": "TEXT",
            "error_message": "TEXT",
        },
        "bcbs239_outputs": {
            "output_name": "TEXT",
            "output_type": "TEXT DEFAULT 'Material Report'",
            "owner": "TEXT",
            "active_flag": "INTEGER DEFAULT 1",
            "maker_checker_comments": "TEXT",
            "created_by": "TEXT",
            "created_at": "TEXT",
            "updated_by": "TEXT",
            "updated_at": "TEXT",
        },
        "reference_data": {
            "category": "TEXT",
            "value": "TEXT",
            "active_flag": "INTEGER DEFAULT 1",
            "maker_checker_comments": "TEXT",
            "proposed_by": "TEXT",
            "approved_by": "TEXT",
            "approval_status": "TEXT DEFAULT 'Approved'",
        },
        "due_date_rules": {
            "task_type": "TEXT",
            "risk_level": "TEXT DEFAULT 'Any'",
            "due_days": "INTEGER DEFAULT 7",
            "active_flag": "INTEGER DEFAULT 1",
            "maker_checker_comments": "TEXT",
            "proposed_by": "TEXT",
            "approved_by": "TEXT",
            "approval_status": "TEXT DEFAULT 'Approved'",
        },
        "required_artifact_rules": {
            "risk_level": "TEXT",
            "lifecycle_stage": "TEXT DEFAULT 'Any'",
            "required_document_type": "TEXT",
            "control_area": "TEXT",
            "cacrt_dimension": "TEXT",
            "mandatory_flag": "INTEGER DEFAULT 1",
            "maker_checker_comments": "TEXT",
            "proposed_by": "TEXT",
            "approved_by": "TEXT",
            "approval_status": "TEXT DEFAULT 'Approved'",
            "what_to_upload": "TEXT",
        },
        "risk_assessments": {
            "materiality_q1": "TEXT",
            "materiality_q2": "TEXT",
            "materiality_q3": "TEXT",
            "materially_supports_bcbs239": "TEXT",
            "owner_integrity_inherent": "TEXT",
            "owner_timeliness_inherent": "TEXT",
            "effective_integrity_inherent": "TEXT",
            "effective_timeliness_inherent": "TEXT",
            "integrity_control_effectiveness": "TEXT",
            "timeliness_control_effectiveness": "TEXT",
            "integrity_residual_risk": "TEXT",
            "timeliness_residual_risk": "TEXT",
            "overall_inherent_risk": "TEXT",
            "overall_residual_risk": "TEXT",
            "required_action": "TEXT",
            "control_registration_risk_assessment": "TEXT",
            "control_privileged_access": "TEXT",
            "control_versioning_change_log": "TEXT",
            "control_checks_reconciliations": "TEXT",
            "control_library_controls_cacrt": "TEXT",
            "control_operating_procedure": "TEXT",
            "control_evidence_signoff": "TEXT",
            "control_resilience": "TEXT",
            "status": "TEXT DEFAULT 'Submitted'",
            "reviewed_by": "TEXT",
            "reviewed_at": "TEXT",
            "review_comments": "TEXT",
            "edit_request_status": "TEXT DEFAULT 'Not Requested'",
            "edit_requested_by": "TEXT",
            "edit_requested_at": "TEXT",
            "edit_request_reason": "TEXT",
            "edit_approved_by": "TEXT",
            "edit_approved_at": "TEXT",
            "edit_approval_comments": "TEXT",
            "last_edited_by": "TEXT",
            "last_edited_at": "TEXT",
        },
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
