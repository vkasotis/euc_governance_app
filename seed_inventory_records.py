"""Seed the EUC Governance app from the uploaded policy-aligned EUC Inventory workbook.

This loader uses a JSON snapshot extracted from `1.EUC_Inventory.xlsx` so the app
can be deployed without requiring Excel-reading libraries at runtime.

Usage:
    python seed_inventory_records.py
    python seed_inventory_records.py --force

`--force` removes existing EUC operational data first but preserves users,
configuration, RACI rules, reference data and audit trail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import db
import services as svc
from db import execute, fetch_one, insert_audit, utc_now

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "inventory_seed_data.json"

EUC_FIELDS = [
    "reference_id", "name", "description", "purpose", "legal_entity", "owner", "owner_delegate", "reviewer",
    "business_unit", "technology_type", "storage_location", "frequency", "schedule", "cut_off", "business_context",
    "supports_material_report", "supports_material_kri", "supports_material_model", "multi_bu_use", "active_user_count",
    "created_by_bu", "acquired_third_party_cots", "support_contract_sla", "last_risk_assessment_date",
    "bcbs239_output_mapping", "cde_linkage", "inputs", "outputs", "recipients", "dependencies", "spof_indicator",
    "inherent_risk", "residual_risk", "overall_status", "documentation_completeness_status", "lifecycle_status",
    "next_review_date", "industrialization_rationale", "decommissioning_rationale", "created_by", "created_at", "updated_at",
    "mapping_na_justification", "onboarding_type", "design_logic_applicable", "design_logic_rationale",
    "euc_operationalization_document_link", "policy242_operationalization_link", "bcbs239_elevated_inherent_override",
    "backup_path_documented", "last_restore_drill_date", "deputy_cover", "knowledge_transfer_evidence", "registration_date",
    "go_live_date", "materiality_criterion_1", "materiality_criterion_2", "materiality_criterion_3", "material_report_mapping",
    "material_kri_mapping", "material_model_mapping", "evidence_pack_location", "library_controls_link", "risk_assessment_link",
    "baseline_controls_complete", "four_eye_review_required", "high_criticality_evidence_pack_required", "access_control_evidence_status",
    "reconciliation_control_evidence_status", "testing_evidence_status", "uat_evidence_status", "approval_signoff_evidence_status",
    "documentation_gap_assessment_required", "documentation_gaps_summary", "remediation_action_owner", "remediation_target_date",
    "incident_near_miss_count", "last_incident_date", "material_mapping_confidence", "migration_status", "migration_notes",
    "legacy_sensitive_data_flag", "legacy_criticality", "critical_dependencies_documented",
]

COMPONENT_FIELDS = [
    "euc_id", "component_name", "component_type", "technology", "storage_location", "description", "criticality", "owner",
    "rrf_mapping", "operationalization_document_link", "file_description", "technology_type", "controlled_storage_type",
    "controlled_storage_location", "input_sources", "asset_cut_off", "processing_schedule", "execution_frequency",
    "cde_mappings", "data_outputs", "level_of_automation", "backup_recovery_arrangements", "spof_risk",
    "modification_date", "review_date", "cots_third_party_component", "vendor_tool_name", "asset_support_contract_sla",
    "vendor_support_status", "end_of_support_date", "approved_corporate_environment", "personal_byod_storage_used",
    "required_input_availability_time", "expected_run_duration", "timeliness_monitoring_performed", "fallback_bcp_steps_link",
    "asset_last_restore_test_date", "asset_deputy_cover", "key_person_dependency_mitigated", "version_release_identifier",
    "change_log_link", "latest_release_notes_link", "retention_evidence_location", "data_classification", "external_sharing",
    "material_mapping_confidence", "asset_migration_status", "asset_migration_notes", "legacy_sensitive_data_flag",
    "legacy_criticality", "legacy_support_contract_sla", "created_at",
]


def _load_payload() -> dict[str, Any]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Inventory seed data file not found: {DATA_FILE}")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _upsert_demo_user(username: str | None, role: str) -> None:
    username = (username or "").strip()
    if not username:
        return
    existing = fetch_one("SELECT user_id FROM user_profiles WHERE username = ?", (username,))
    if existing:
        return
    now = utc_now()
    execute(
        """
        INSERT INTO user_profiles(
            username, full_name, email, role, active_flag, maker_checker_comments,
            created_by, created_at, updated_by, updated_at
        ) VALUES (?, ?, ?, ?, 1, ?, 'inventory_import', ?, 'inventory_import', ?)
        """,
        (
            username,
            username,
            svc.DEFAULT_EMAIL_ADDRESS,
            role,
            "Created automatically from imported EUC Inventory owner/reviewer values.",
            now,
            now,
        ),
    )


def _insert_euc(row: dict[str, Any]) -> int:
    existing = fetch_one("SELECT euc_id FROM eucs WHERE reference_id = ?", (row["reference_id"],))
    if existing:
        return int(existing["euc_id"])
    now = utc_now()
    values = {**row, "created_by": "inventory_import", "created_at": now, "updated_at": now}
    placeholders = ", ".join("?" for _ in EUC_FIELDS)
    euc_id = execute(
        f"INSERT INTO eucs({', '.join(EUC_FIELDS)}) VALUES ({placeholders})",
        tuple(values.get(field) for field in EUC_FIELDS),
    )
    insert_audit("EUC", euc_id, "IMPORT", "inventory_import", None, {"reference_id": row.get("reference_id"), "source": "1.EUC_Inventory.xlsx"})
    return int(euc_id)


def _insert_component(row: dict[str, Any], euc_ids_by_ref: dict[str, int]) -> int:
    source_asset_id = row.pop("source_asset_id", None)
    parent_ref = row.pop("parent_reference_id")
    euc_id = euc_ids_by_ref[parent_ref]
    existing = None
    if source_asset_id:
        existing = fetch_one(
            """
            SELECT component_id FROM components
            WHERE euc_id = ? AND COALESCE(asset_migration_notes, '') LIKE ?
            LIMIT 1
            """,
            (euc_id, f"%Imported source Asset ID: {source_asset_id}.%"),
        )
    if existing:
        return int(existing["component_id"])
    now = utc_now()
    values = {**row, "euc_id": euc_id, "created_at": now}
    fields = COMPONENT_FIELDS
    placeholders = ", ".join("?" for _ in fields)
    component_id = execute(
        f"INSERT INTO components({', '.join(fields)}) VALUES ({placeholders})",
        tuple(values.get(field) for field in fields),
    )
    insert_audit(
        "Component",
        component_id,
        "IMPORT",
        "inventory_import",
        None,
        {"source_asset_id": source_asset_id, "parent_reference_id": parent_ref, "source": "1.EUC_Inventory.xlsx"},
    )
    return int(component_id)


def seed_inventory(force: bool = False) -> dict[str, int]:
    payload = _load_payload()
    db.init_db()
    svc.initialize_reference_data("inventory_import")

    if force:
        svc.delete_all_euc_operational_data("inventory_import")

    for row in payload["eucs"]:
        _upsert_demo_user(row.get("owner"), svc.OWNER_ROLE)
        _upsert_demo_user(row.get("owner_delegate"), svc.CONTRIBUTOR_ROLE)
        _upsert_demo_user(row.get("reviewer"), svc.CONTRIBUTOR_ROLE)
    _upsert_demo_user("Inventory Import Owner", svc.OWNER_ROLE)

    euc_ids_by_ref: dict[str, int] = {}
    for row in payload["eucs"]:
        euc_id = _insert_euc(dict(row))
        euc_ids_by_ref[row["reference_id"]] = euc_id

    for row in payload["assets"]:
        parent_ref = row.get("parent_reference_id")
        if parent_ref not in euc_ids_by_ref:
            parent_ref = "EUC.IMPORT.UNMATCHED"
            row = {**row, "parent_reference_id": parent_ref}
        _insert_component(dict(row), euc_ids_by_ref)

    summary = {
        "eucs": db.table_count("eucs"),
        "components": db.table_count("components"),
        "orphan_assets": int(payload.get("metadata", {}).get("orphan_assets") or 0),
    }
    insert_audit("Inventory Import", "1.EUC_Inventory.xlsx", "IMPORT_COMPLETE", "inventory_import", None, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed EUC Governance app records from 1.EUC_Inventory.xlsx snapshot.")
    parser.add_argument("--force", action="store_true", help="Delete existing EUC operational data before loading the inventory records.")
    args = parser.parse_args()
    summary = seed_inventory(force=args.force)
    print("Inventory import completed:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
