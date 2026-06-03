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

    Each CREATE TABLE and CREATE INDEX statement is executed individually and
    logged if it fails. This makes clean-deployment startup errors diagnosable
    from Streamlit Cloud logs instead of surfacing only a redacted UI error.
    """
    with get_connection() as conn:
        for i, stmt in enumerate(CREATE_TABLES_SQL, start=1):
            try:
                conn.execute(stmt)
            except Exception as exc:
                print("\n" + "=" * 100)
                print(f"FAILED CREATE_TABLES_SQL statement #{i}")
                print(type(exc).__name__, str(exc))
                print("-" * 100)
                print(stmt)
                print("=" * 100 + "\n")
                raise

        _apply_lightweight_migrations(conn)

        for i, stmt in enumerate(INDEX_SQL, start=1):
            try:
                conn.execute(stmt)
            except Exception as exc:
                print("\n" + "=" * 100)
                print(f"FAILED INDEX_SQL statement #{i}")
                print(type(exc).__name__, str(exc))
                print("-" * 100)
                print(stmt)
                print("=" * 100 + "\n")
                raise


def _apply_lightweight_migrations(conn: sqlite3.Connection) -> None:
    """Add MVP columns when a previous local DB already exists."""
    expected_columns = {
        "eucs": {
            "reference_id": "TEXT",
            "name": "TEXT",
            "description": "TEXT",
            "purpose": "TEXT",
            "legal_entity": "TEXT",
            "owner": "TEXT",
            "owner_delegate": "TEXT",
            "reviewer": "TEXT",
            "business_unit": "TEXT",
            "technology_type": "TEXT",
            "storage_location": "TEXT",
            "frequency": "TEXT",
            "schedule": "TEXT",
            "cut_off": "TEXT",
            "business_context": "TEXT",
            "supports_material_report": "TEXT DEFAULT 'No'",
            "supports_material_kri": "TEXT DEFAULT 'No'",
            "supports_material_model": "TEXT DEFAULT 'No'",
            "multi_bu_use": "TEXT",
            "active_user_count": "INTEGER",
            "created_by_bu": "TEXT",
            "acquired_third_party_cots": "TEXT",
            "support_contract_sla": "TEXT",
            "last_risk_assessment_date": "TEXT",
            "bcbs239_output_mapping": "TEXT",
            "cde_linkage": "TEXT",
            "inputs": "TEXT",
            "outputs": "TEXT",
            "recipients": "TEXT",
            "dependencies": "TEXT",
            "spof_indicator": "TEXT DEFAULT 'No'",
            "inherent_risk": "TEXT DEFAULT 'Medium'",
            "residual_risk": "TEXT DEFAULT 'Medium'",
            "overall_status": "TEXT DEFAULT 'Draft'",
            "documentation_completeness_status": "TEXT DEFAULT 'Not Checked'",
            "lifecycle_status": "TEXT DEFAULT 'Draft'",
            "next_review_date": "TEXT",
            "industrialization_rationale": "TEXT",
            "decommissioning_rationale": "TEXT",
            "created_by": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
            "mapping_na_justification": "TEXT",
            "legacy_onboarding": "INTEGER DEFAULT 0",
            "onboarding_type": "TEXT DEFAULT 'New EUC'",
            "design_logic_applicable": "TEXT DEFAULT 'No'",
            "design_logic_rationale": "TEXT",
            "euc_operationalization_document_link": "TEXT",
            "policy242_operationalization_link": "TEXT",
            "bcbs239_elevated_inherent_override": "TEXT DEFAULT 'No'",
            "backup_path_documented": "TEXT",
            "last_restore_drill_date": "TEXT",
            "deputy_cover": "TEXT",
            "knowledge_transfer_evidence": "TEXT",
            "registration_date": "TEXT",
            "go_live_date": "TEXT",
            "materiality_criterion_1": "TEXT",
            "materiality_criterion_2": "TEXT",
            "materiality_criterion_3": "TEXT",
            "material_report_mapping": "TEXT",
            "material_kri_mapping": "TEXT",
            "material_model_mapping": "TEXT",
            "evidence_pack_location": "TEXT",
            "library_controls_link": "TEXT",
            "risk_assessment_link": "TEXT",
            "baseline_controls_complete": "TEXT",
            "four_eye_review_required": "TEXT",
            "high_criticality_evidence_pack_required": "TEXT",
            "access_control_evidence_status": "TEXT",
            "reconciliation_control_evidence_status": "TEXT",
            "testing_evidence_status": "TEXT",
            "uat_evidence_status": "TEXT",
            "approval_signoff_evidence_status": "TEXT",
            "documentation_gap_assessment_required": "TEXT",
            "documentation_gaps_summary": "TEXT",
            "remediation_action_owner": "TEXT",
            "remediation_target_date": "TEXT",
            "incident_near_miss_count": "INTEGER DEFAULT 0",
            "last_incident_date": "TEXT",
            "material_mapping_confidence": "TEXT",
            "migration_status": "TEXT",
            "migration_notes": "TEXT",
            "legacy_sensitive_data_flag": "TEXT",
            "legacy_criticality": "TEXT",
            "critical_dependencies_documented": "TEXT",
        },
        "documents": {
            "deficiency_tag": "TEXT",
            "evidence_group_id": "TEXT",
        },
        "components": {
            "rrf_mapping": "TEXT",
            "operationalization_document_link": "TEXT",
            "file_description": "TEXT",
            "technology_type": "TEXT",
            "controlled_storage_type": "TEXT",
            "controlled_storage_location": "TEXT",
            "input_sources": "TEXT",
            "asset_cut_off": "TEXT",
            "cut_off": "TEXT",
            "processing_schedule": "TEXT",
            "execution_frequency": "TEXT",
            "cde_mappings": "TEXT",
            "data_outputs": "TEXT",
            "level_of_automation": "TEXT",
            "backup_recovery_arrangements": "TEXT",
            "spof_risk": "TEXT",
            "modification_date": "TEXT",
            "review_date": "TEXT",
            "cots_third_party_component": "TEXT",
            "vendor_tool_name": "TEXT",
            "asset_support_contract_sla": "TEXT",
            "vendor_support_status": "TEXT",
            "end_of_support_date": "TEXT",
            "approved_corporate_environment": "TEXT",
            "personal_byod_storage_used": "TEXT",
            "required_input_availability_time": "TEXT",
            "expected_run_duration": "TEXT",
            "timeliness_monitoring_performed": "TEXT",
            "fallback_bcp_steps_link": "TEXT",
            "asset_last_restore_test_date": "TEXT",
            "asset_deputy_cover": "TEXT",
            "key_person_dependency_mitigated": "TEXT",
            "version_release_identifier": "TEXT",
            "change_log_link": "TEXT",
            "latest_release_notes_link": "TEXT",
            "retention_evidence_location": "TEXT",
            "data_classification": "TEXT",
            "external_sharing": "TEXT",
            "material_mapping_confidence": "TEXT",
            "asset_migration_status": "TEXT",
            "asset_migration_notes": "TEXT",
            "legacy_sensitive_data_flag": "TEXT",
            "legacy_criticality": "TEXT",
            "legacy_support_contract_sla": "TEXT",
        },
        "exceptions": {"closure_evidence_document_id": "INTEGER",
            "exception_owner": "TEXT",
            "milestones": "TEXT",
            "monitoring_approach": "TEXT",
            "periodic_review_date": "TEXT",
            "renewal_status": "TEXT",
            "renewal_request_reason": "TEXT",
            "renewal_evidence_document_id": "INTEGER",
            "escalation_required": "TEXT",
            "escalation_to": "TEXT",
            "escalation_date": "TEXT",
            "senior_management_approval": "TEXT",
            "bcbs239_steering_reported": "TEXT",
            "unit_head_approval": "TEXT",
        },
        "incidents": {
            "detection_date": "TEXT",
            "reporting_period_run": "TEXT",
            "reported_by": "TEXT",
            "incident_type": "TEXT",
            "incident_description": "TEXT",
            "impact_description": "TEXT",
            "severity": "TEXT",
            "cacrt_dimension": "TEXT",
            "root_cause_category": "TEXT",
            "root_cause_description": "TEXT",
            "immediate_action_taken": "TEXT",
            "corrective_action": "TEXT",
            "preventive_action": "TEXT",
            "action_owner": "TEXT",
            "target_resolution_date": "TEXT",
            "resolution_date": "TEXT",
            "linked_residual_risk_level": "TEXT",
            "regulatory_impact": "TEXT",
            "escalated": "TEXT",
            "escalation_date": "TEXT",
            "escalation_to": "TEXT",
            "restatement_reissue_required": "TEXT",
            "exception_raised": "TEXT",
            "reference_links_evidence": "TEXT",
            "comments": "TEXT",
        },
        "material_changes": {
            "change_request_rationale": "TEXT",
            "cutover_plan": "TEXT",
            "rollback_approach": "TEXT",
            "change_stage": "TEXT",
            "testing_required": "INTEGER DEFAULT 0",
            "uat_required": "INTEGER DEFAULT 0",
            "approval_required": "INTEGER DEFAULT 0",
            "approval_status": "TEXT",
            "approved_by": "TEXT",
            "approval_date": "TEXT",
            "library_controls_update_required": "INTEGER DEFAULT 0",
            "evidence_pack_update_detail": "TEXT",
            "stakeholder_communication": "TEXT",
            "communication_date": "TEXT",
            "effective_date": "TEXT",
            "emergency_change": "INTEGER DEFAULT 0",
            "retro_uat_required": "INTEGER DEFAULT 0",
        },
        "documentation_gaps": {
            "gap_area": "TEXT",
            "gap_description": "TEXT",
            "related_artifact": "TEXT",
            "severity": "TEXT",
            "owner": "TEXT",
            "target_date": "TEXT",
            "disposition": "TEXT",
            "status": "TEXT",
            "exception_id": "INTEGER",
            "task_id": "INTEGER",
            "created_by": "TEXT",
            "created_at": "TEXT",
            "closed_at": "TEXT",
            "closure_comments": "TEXT",
        },
        "high_criticality_reviews": {
            "reviewer": "TEXT",
            "review_date": "TEXT",
            "mandatory_flag": "INTEGER DEFAULT 0",
            "overview_governance": "TEXT",
            "scope_purpose": "TEXT",
            "lineage_data": "TEXT",
            "design_logic": "TEXT",
            "controls_reconciliations": "TEXT",
            "testing_sufficiency": "TEXT",
            "security_access": "TEXT",
            "resilience": "TEXT",
            "independent_review_conclusion": "TEXT",
            "controls_evidence_index": "TEXT",
            "overall_outcome": "TEXT",
            "comments": "TEXT",
            "created_at": "TEXT",
        },
        "industrialization_assessments": {
            "bcbs_score": "INTEGER DEFAULT 0",
            "residual_score": "INTEGER DEFAULT 0",
            "operational_score": "INTEGER DEFAULT 0",
            "frequency_volume_score": "INTEGER DEFAULT 0",
            "strategic_fit_score": "INTEGER DEFAULT 0",
            "total_score": "INTEGER DEFAULT 0",
            "priority_band": "TEXT",
            "decision": "TEXT",
            "decision_rationale": "TEXT",
            "assessed_by": "TEXT",
            "assessment_date": "TEXT",
            "created_at": "TEXT",
        },
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
        "custom_report_definitions": {
            "report_name": "TEXT",
            "description": "TEXT",
            "dataset": "TEXT",
            "selected_columns": "TEXT",
            "filters_json": "TEXT",
            "active_flag": "INTEGER DEFAULT 1",
            "created_by": "TEXT",
            "created_at": "TEXT",
            "updated_by": "TEXT",
            "updated_at": "TEXT",
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
