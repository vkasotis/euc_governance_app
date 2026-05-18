"""Business services and governance rules for the EUC Governance MVP."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from db import UPLOAD_PATH, dataframe, execute, fetch_all, fetch_one, insert_audit, utc_now
from schema import (
    AUTOMATION_LEVELS,
    BASELINE_CONTROL_AREAS,
    CACRT_DIMENSIONS,
    CONTROL_AREAS,
    CONTROL_EFFECTIVENESS_LEVELS,
    CONTROL_STATUSES,
    DEFAULT_REQUIRED_ARTIFACTS,
    DOCUMENT_TYPES,
    FREQUENCIES,
    LEGAL_ENTITIES,
    LIFECYCLE_STATUSES,
    RISK_ASSESSMENT_TYPES,
    RISK_LEVELS,
    ROLES,
    TASK_TYPES,
    TECHNOLOGY_TYPES,
)

OPEN_TASK_STATUSES = ("Open", "In Progress", "Blocked", "Closure Requested")
READ_ONLY_ROLE = "Internal Audit / Read-only User"
ADMIN_ROLE = "Group IT Governance Administrator"
GCC_ROLE = "GCC"
DVU_ROLE = "Data Validation Unit"
APPROVER_ROLE = "Approver / Head of Unit"
OWNER_ROLE = "EUC Owner"
CONTRIBUTOR_ROLE = "EUC Owner Delegate / Contributor"

DEFAULT_USER_PROFILES = [
    {"username": "Maria.Papadopoulou", "full_name": "Maria Papadopoulou", "email": "maria.papadopoulou@eurobank.gr", "role": OWNER_ROLE},
    {"username": "Nikos.Georgiou", "full_name": "Nikos Georgiou", "email": "nikos.georgiou@eurobank.gr", "role": OWNER_ROLE},
    {"username": "Elena.Dimitriou", "full_name": "Elena Dimitriou", "email": "elena.dimitriou@eurobank.gr", "role": OWNER_ROLE},
    {"username": "Kostas.Ioannou", "full_name": "Kostas Ioannou", "email": "kostas.ioannou@eurobank.gr", "role": OWNER_ROLE},
    {"username": "EUC.Contributor", "full_name": "EUC Contributor", "email": "euc.contributor@eurobank.gr", "role": CONTRIBUTOR_ROLE},
    {"username": "Christina.Markou", "full_name": "Christina Markou", "email": "christina.markou@eurobank.gr", "role": CONTRIBUTOR_ROLE},
    {"username": "GCC.User", "full_name": "GCC User", "email": "gcc.user@eurobank.gr", "role": GCC_ROLE},
    {"username": "GCC.Monitor", "full_name": "GCC Monitor", "email": "gcc.monitor@eurobank.gr", "role": GCC_ROLE},
    {"username": "DVU.Reviewer", "full_name": "Data Validation Reviewer", "email": "dvu.reviewer@eurobank.gr", "role": DVU_ROLE},
    {"username": "Data.Validation", "full_name": "Data Validation Unit", "email": "data.validation@eurobank.gr", "role": DVU_ROLE},
    {"username": "Admin.User", "full_name": "Admin User", "email": "admin.user@eurobank.gr", "role": ADMIN_ROLE},
    {"username": "IT.Governance.Admin", "full_name": "IT Governance Admin", "email": "it.governance.admin@eurobank.gr", "role": ADMIN_ROLE},
    {"username": "Head.Of.Unit", "full_name": "Head of Unit", "email": "head.of.unit@eurobank.gr", "role": APPROVER_ROLE},
    {"username": "Approver.User", "full_name": "Approver User", "email": "approver.user@eurobank.gr", "role": APPROVER_ROLE},
    {"username": "Internal.Audit", "full_name": "Internal Audit", "email": "internal.audit@eurobank.gr", "role": READ_ONLY_ROLE},
    {"username": "Read.Only", "full_name": "Read Only User", "email": "read.only@eurobank.gr", "role": READ_ONLY_ROLE},
]

ROLE_USERNAMES = {}
for _profile in DEFAULT_USER_PROFILES:
    ROLE_USERNAMES.setdefault(_profile["role"], []).append(_profile["username"])

DEFAULT_DUE_DAYS = {
    "Registration completion": 7,
    "Risk assessment": 10,
    "Document submission": 14,
    "Missing evidence": 10,
    "Remediation": 30,
    "Reassessment": 15,
    "Review response": 10,
    "Closure evidence": 10,
    "Documentation refresh": 15,
}

RISK_RANK = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
RANK_RISK = {v: k for k, v in RISK_RANK.items()}
CONTROL_EFFECTIVENESS_RANK = {"Not in place": 0, "Weak": 1, "Adequate": 2, "Strong": 3}

# Residual Risk Calculation Matrix from the uploaded EUC Risk Assessment workbook.
# Rows are effective inherent risk levels; columns are derived control effectiveness levels.
RESIDUAL_RISK_MATRIX = {
    "Very High": {"Strong": "Medium", "Adequate": "High", "Weak": "Very High", "Not in place": "Very High"},
    "High": {"Strong": "Low", "Adequate": "Medium", "Weak": "High", "Not in place": "High"},
    "Medium": {"Strong": "Low", "Adequate": "Low", "Weak": "Medium", "Not in place": "Medium"},
    "Low": {"Strong": "Low", "Adequate": "Low", "Weak": "Low", "Not in place": "Low"},
}

CONTROL_DEFAULT_MEANINGS = {
    "1. Registration & risk assessment": "EUC registered; latest risk assessment completed; inventory current.",
    "2. Privileged Access": "Named roles assigned; access reviewed; unauthorized access prevented.",
    "3. Versioning & change log": "Controlled repository used; release versions tagged; material changes traceable.",
    "4. Checks & reconciliations": "Input validation, timeliness checks and reconciliations operate with evidence.",
    "5. EUC Library of Controls (CACRT)": "CACRT controls documented with owner, frequency, thresholds, evidence links.",
    "6. Operating Procedure": "Current runbook/operating procedure exists and aligns to RRF operationalisation where applicable.",
    "7. Evidence & sign-off": "Testing, UAT, and sign-offs retained to support control-effectiveness ratings.",
    "8. Resilience": "Backup, restore, fallback steps, recoverability evidence, and deputy cover are in place where needed.",
}

INTEGRITY_CONTROL_KEYS = [
    "1. Registration & risk assessment",
    "2. Privileged Access",
    "3. Versioning & change log",
    "4. Checks & reconciliations",
    "5. EUC Library of Controls (CACRT)",
    "6. Operating Procedure",
    "7. Evidence & sign-off",
]

TIMELINESS_CONTROL_KEYS = [
    "1. Registration & risk assessment",
    "2. Privileged Access",
    "5. EUC Library of Controls (CACRT)",
    "7. Evidence & sign-off",
    "8. Resilience",
]

# The workbook allows N/A only for EUC Library of Controls / CACRT and Evidence & sign-off.
NA_ALLOWED_CONTROL_KEYS = {
    "5. EUC Library of Controls (CACRT)",
    "7. Evidence & sign-off",
}

OWNER_INHERENT_LEVELS = ["Low", "Medium", "High"]


def username_options_for_role(role: str) -> list[str]:
    db_users = dataframe(
        "SELECT username FROM user_profiles WHERE role = ? AND active_flag = 1 ORDER BY username",
        (role,),
    )
    if not db_users.empty:
        return db_users["username"].tolist()
    return ROLE_USERNAMES.get(role, ["Demo.User"])


def seed_user_profiles(username: str = "system") -> None:
    """Seed and maintain the local user/email directory used for task routing."""
    now = utc_now()
    for profile in DEFAULT_USER_PROFILES:
        execute(
            """
            INSERT OR IGNORE INTO user_profiles(username, full_name, email, role, active_flag, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (profile["username"], profile["full_name"], profile["email"], profile["role"], now, now),
        )


def user_directory(role: str | None = None, active_only: bool = True) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if role:
        where.append("role = ?")
        params.append(role)
    if active_only:
        where.append("active_flag = 1")
    sql = "SELECT user_id, username, full_name, email, role, active_flag, created_at, updated_at FROM user_profiles"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY role, full_name, username"
    return dataframe(sql, tuple(params))


def get_user_profile(username: str | None) -> dict[str, Any] | None:
    if not username:
        return None
    return fetch_one("SELECT * FROM user_profiles WHERE username = ?", (username,))


def _validate_user_profile_payload(payload: dict[str, Any]) -> None:
    """Validate the local MVP user directory record."""
    required = ["username", "full_name", "email", "role"]
    missing = [field for field in required if not str(payload.get(field, "")).strip()]
    if missing:
        raise ValueError("Missing mandatory user fields: " + ", ".join(missing))
    if "@" not in str(payload.get("email", "")):
        raise ValueError("A valid email address is required.")
    if payload.get("role") not in ROLES:
        raise ValueError("Role is not valid for this application.")


def update_user_profile(user_id: int, payload: dict[str, Any], performed_by: str) -> int:
    """Update a selected user profile by stable user_id.

    This supports table-driven editing in Admin Configuration and avoids
    accidentally creating a second user when an administrator edits the
    username of an existing profile.
    """
    _validate_user_profile_payload(payload)
    old = fetch_one("SELECT * FROM user_profiles WHERE user_id = ?", (int(user_id),))
    if not old:
        raise ValueError("Selected user profile no longer exists.")
    duplicate = fetch_one(
        "SELECT user_id FROM user_profiles WHERE username = ? AND user_id <> ?",
        (payload["username"], int(user_id)),
    )
    if duplicate:
        raise ValueError("Another user profile already uses this username.")
    now = utc_now()
    execute(
        """
        UPDATE user_profiles
        SET username = ?, full_name = ?, email = ?, role = ?, active_flag = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (
            payload["username"],
            payload["full_name"],
            payload["email"],
            payload["role"],
            int(bool(payload.get("active_flag", True))),
            now,
            int(user_id),
        ),
    )
    new_snapshot = dict(payload)
    new_snapshot.update({"user_id": int(user_id), "updated_at": now})
    insert_audit("User Profile", int(user_id), "UPDATE", performed_by, old, new_snapshot)
    return int(user_id)


def upsert_user_profile(payload: dict[str, Any], performed_by: str) -> int:
    _validate_user_profile_payload(payload)
    old = get_user_profile(payload["username"])
    now = utc_now()
    if old:
        return update_user_profile(int(old["user_id"]), payload, performed_by)
    user_id = execute(
        """
        INSERT INTO user_profiles(username, full_name, email, role, active_flag, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["username"],
            payload["full_name"],
            payload["email"],
            payload["role"],
            int(bool(payload.get("active_flag", True))),
            now,
            now,
        ),
    )
    insert_audit("User Profile", user_id, "CREATE", performed_by, None, payload)
    return user_id


def is_read_only(role: str) -> bool:
    return role == READ_ONLY_ROLE


def can_view_all(role: str) -> bool:
    return role in {ADMIN_ROLE, GCC_ROLE, DVU_ROLE, APPROVER_ROLE, READ_ONLY_ROLE}


def can_view_all_eucs(role: str) -> bool:
    """Portfolio-wide EUC visibility.

    EUC Owners and Contributors see only EUCs where they are owner, delegate,
    or creator. GCC, Data Validation, IT Governance Admin, and Internal Audit
    can view the full EUC portfolio. Approvers retain approval workflows but
    do not receive blanket inventory visibility in the MVP.
    """
    return role in {ADMIN_ROLE, GCC_ROLE, DVU_ROLE, READ_ONLY_ROLE}


def can_configure(role: str) -> bool:
    return role == ADMIN_ROLE


def can_delete_records(role: str) -> bool:
    """Governed hard-delete authority for MVP records.

    Deletes are restricted to GCC and Group IT Governance Administrator and
    always create an immutable audit-trail DELETE event before the row is
    removed. This keeps demo data manageable while preserving accountability.
    """
    return role in {GCC_ROLE, ADMIN_ROLE}


def can_review(role: str) -> bool:
    return role in {GCC_ROLE, DVU_ROLE, ADMIN_ROLE}


def can_approve(role: str) -> bool:
    return role in {APPROVER_ROLE, ADMIN_ROLE}


def can_edit_euc(role: str, username: str, euc: dict[str, Any] | None) -> bool:
    if not euc or is_read_only(role):
        return False
    if role == ADMIN_ROLE:
        return True
    if role == OWNER_ROLE and euc.get("owner") == username:
        return True
    if role == CONTRIBUTOR_ROLE and euc.get("owner_delegate") == username:
        return True
    return False


def can_upload_evidence(role: str, username: str, euc: dict[str, Any] | None) -> bool:
    return can_edit_euc(role, username, euc) or role in {GCC_ROLE, DVU_ROLE, ADMIN_ROLE}


def add_days(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def risk_level_from_average(avg: float) -> str:
    """Legacy fallback scoring rule retained for old seed payloads and migrations."""
    if avg < 2.0:
        return "Low"
    if avg < 3.0:
        return "Medium"
    if avg < 4.0:
        return "High"
    return "Very High"


def score_to_risk_level(score: int | float | str | None) -> str:
    try:
        score_f = float(score or 2)
    except (TypeError, ValueError):
        return str(score) if score in RISK_RANK else "Medium"
    return risk_level_from_average(score_f)


def risk_rank(level: str | None) -> int:
    return RISK_RANK.get(str(level or "Medium"), 2)


def highest_risk_level(levels: list[str]) -> str:
    return RANK_RISK.get(max(risk_rank(level) for level in levels), "Medium")


def material_supports_bcbs239(q1: str | None, q2: str | None, q3: str | None) -> str:
    return "Yes" if any(str(v).strip().lower() == "yes" for v in [q1, q2, q3]) else "No"


def derive_control_effectiveness(statuses: list[str]) -> str:
    """Replicates the workbook LET formulas for derived control effectiveness."""
    normalized = [status if status in CONTROL_STATUSES else "Not in place" for status in statuses]
    not_in = normalized.count("Not in place")
    partial = normalized.count("Partially in place")
    evidenced = normalized.count("In place and evidenced")
    total = len(normalized)
    if not_in >= 2:
        return "Not in place"
    if not_in == 1:
        return "Weak"
    if partial == total:
        return "Weak"
    if evidenced > total / 2:
        return "Strong"
    if evidenced >= 1:
        return "Adequate"
    return "Adequate"


def residual_from_matrix(effective_inherent: str, control_effectiveness: str) -> str:
    return RESIDUAL_RISK_MATRIX.get(effective_inherent, RESIDUAL_RISK_MATRIX["Medium"]).get(control_effectiveness, "Medium")


def required_action_guidance(residual_risk: str) -> str:
    if residual_risk == "Very High":
        return "Outside tolerance: escalation and time-bound remediation required; do not operate material-report EUCs with unmitigated Very High residual risk."
    if residual_risk == "High":
        return "Remediation plan required with target dates; consider exception governance if temporary operation is needed."
    if residual_risk == "Medium":
        return "Operate with monitoring and timely remediation of gaps."
    return "Maintain controls and reassess on change."


def calculate_policy_risk(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate EUC risk using the uploaded Risk Assessment workbook methodology.

    The workbook keeps the owner-entered inherent risk separate from the
    calculated effective inherent risk. Owner levels are Low/Medium/High only.
    If any BCBS 239 materiality question is Yes, both effective inherent-risk
    dimensions are forced to Very High while the original owner selections are
    retained for auditability.
    """
    q1 = payload.get("materiality_q1", "No")
    q2 = payload.get("materiality_q2", "No")
    q3 = payload.get("materiality_q3", "No")
    # Excel B10 = IF(COUNTIF(B7:B9,"Yes")>0,"Yes","No").
    # The three materiality questions are the source of truth.
    material = material_supports_bcbs239(q1, q2, q3)

    owner_integrity = payload.get("owner_integrity_level") or score_to_risk_level(payload.get("integrity_accuracy_score"))
    owner_timeliness = payload.get("owner_timeliness_level") or score_to_risk_level(payload.get("timeliness_availability_score"))
    # Owner dropdown in the workbook excludes Very High. Normalize legacy values.
    if owner_integrity == "Very High":
        owner_integrity = "High"
    if owner_timeliness == "Very High":
        owner_timeliness = "High"

    # Workbook rule: if material = Yes, C22/C23 become Very High; B22/B23 remain
    # the owner's Low/Medium/High selections.
    if material == "Yes":
        effective_integrity = "Very High"
        effective_timeliness = "Very High"
    else:
        effective_integrity = owner_integrity
        effective_timeliness = owner_timeliness

    controls = payload.get("controls") or {}
    if not isinstance(controls, dict):
        controls = {}
    # Backwards-compatible default: treat missing controls as in place and evidenced unless explicitly supplied.
    control_statuses = {
        control: controls.get(control, {}).get("status") if isinstance(controls.get(control), dict) else controls.get(control)
        for control in BASELINE_CONTROL_AREAS
    }
    for control in BASELINE_CONTROL_AREAS:
        control_statuses[control] = control_statuses.get(control) or payload.get(f"control_{BASELINE_CONTROL_AREAS.index(control) + 1}_status") or "In place and evidenced"
        if control_statuses[control] == "N/A" and control not in NA_ALLOWED_CONTROL_KEYS:
            # Defensive normalization for non-UI/API payloads. The Streamlit UI
            # does not offer N/A for these controls.
            control_statuses[control] = "Not in place"

    integrity_ce = derive_control_effectiveness([control_statuses[c] for c in INTEGRITY_CONTROL_KEYS])
    timeliness_ce = derive_control_effectiveness([control_statuses[c] for c in TIMELINESS_CONTROL_KEYS])
    integrity_residual = residual_from_matrix(effective_integrity, integrity_ce)
    timeliness_residual = residual_from_matrix(effective_timeliness, timeliness_ce)
    inherent = highest_risk_level([effective_integrity, effective_timeliness])
    raw_residual = highest_risk_level([integrity_residual, timeliness_residual])
    residual = raw_residual
    # Workbook rule: material BCBS-supporting EUCs do not land below Medium residual risk.
    if material == "Yes" and risk_rank(residual) < risk_rank("Medium"):
        residual = "Medium"
    return {
        "materially_supports_bcbs239": material,
        "owner_integrity_level": owner_integrity,
        "owner_timeliness_level": owner_timeliness,
        "effective_integrity_level": effective_integrity,
        "effective_timeliness_level": effective_timeliness,
        "integrity_control_effectiveness": integrity_ce,
        "timeliness_control_effectiveness": timeliness_ce,
        "integrity_residual_level": integrity_residual,
        "timeliness_residual_level": timeliness_residual,
        "inherent_risk": inherent,
        "residual_risk": residual,
        "required_action_guidance": required_action_guidance(residual),
        "control_statuses": control_statuses,
    }


def generate_reference_id() -> str:
    row = fetch_one("SELECT COALESCE(MAX(euc_id), 0) + 1 AS next_id FROM eucs")
    # The uploaded inventory workbook uses EUC.001-style references.
    return f"EUC.{int(row['next_id']):03d}"


def all_eucs(role: str | None = None, username: str | None = None) -> pd.DataFrame:
    if role and username and not can_view_all_eucs(role):
        return dataframe(
            """
            SELECT * FROM eucs
            WHERE owner = ? OR owner_delegate = ? OR created_by = ?
            ORDER BY euc_id DESC
            """,
            (username, username, username),
        )
    return dataframe("SELECT * FROM eucs ORDER BY euc_id DESC")


def get_euc(euc_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM eucs WHERE euc_id = ?", (euc_id,))


def get_euc_by_reference(reference_id: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM eucs WHERE reference_id = ?", (reference_id,))


def detect_duplicates(name: str, owner: str, business_unit: str, storage_location: str, exclude_euc_id: int | None = None) -> pd.DataFrame:
    """Simple duplicate heuristic using name tokens, owner, business unit, and storage path."""
    name_token = f"%{(name or '').strip()[:8]}%" if name else "%"
    params: list[Any] = [name_token, owner, business_unit, storage_location]
    sql = """
        SELECT euc_id, reference_id, name, owner, business_unit, storage_location, lifecycle_status, residual_risk
        FROM eucs
        WHERE lower(name) LIKE lower(?)
           OR owner = ?
           OR business_unit = ?
           OR storage_location = ?
    """
    if exclude_euc_id:
        sql += " AND euc_id <> ?"
        params.append(exclude_euc_id)
    sql += " ORDER BY updated_at DESC"
    return dataframe(sql, tuple(params))


def validate_mapping_fields(payload: dict[str, Any]) -> list[str]:
    errors = []
    if not payload.get("bcbs239_output_mapping"):
        errors.append("BCBS 239 output mapping is required.")
    mapping_fields = ["bcbs239_output_mapping", "inputs", "outputs", "recipients", "dependencies"]
    has_na = any(str(payload.get(field, "")).strip().lower() == "not applicable" for field in mapping_fields)
    if has_na and not payload.get("mapping_na_justification"):
        errors.append("A justification is required when a mapping field is marked Not Applicable.")
    return errors


def create_euc(payload: dict[str, Any], username: str) -> int:
    mandatory = ["name", "owner", "business_unit", "technology_type", "storage_location", "bcbs239_output_mapping"]
    missing = [field for field in mandatory if not str(payload.get(field, "")).strip()]
    errors = [f"Missing mandatory field: {field}" for field in missing] + validate_mapping_fields(payload)
    if errors:
        raise ValueError("\n".join(errors))

    material = material_supports_bcbs239(
        payload.get("supports_material_report"),
        payload.get("supports_material_kri"),
        payload.get("supports_material_model"),
    )
    now = utc_now()
    reference_id = generate_reference_id()
    euc_id = execute(
        """
        INSERT INTO eucs(
            reference_id, name, description, purpose, legal_entity, owner, owner_delegate, reviewer, business_unit,
            technology_type, storage_location, frequency, schedule, cut_off, business_context, bcbs239_output_mapping,
            cde_linkage, inputs, outputs, recipients, dependencies, spof_indicator, supports_material_report,
            supports_material_kri, supports_material_model, used_by_multiple_bus, number_active_users, created_by_bu,
            acquired_third_party, support_contract_sla, library_of_controls, last_risk_assessment,
            exceptions_remediation_actions, industrialization_decommissioning_status, materially_supports_bcbs239,
            materiality_rationale, inherent_risk, residual_risk, overall_status, documentation_completeness_status,
            lifecycle_status, next_review_date, industrialization_rationale, decommissioning_rationale, created_by,
            created_at, updated_at, mapping_na_justification
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            reference_id,
            payload.get("name"),
            payload.get("description"),
            payload.get("purpose"),
            payload.get("legal_entity", "Eurobank S.A."),
            payload.get("owner"),
            payload.get("owner_delegate"),
            payload.get("reviewer"),
            payload.get("business_unit"),
            payload.get("technology_type"),
            payload.get("storage_location"),
            payload.get("frequency"),
            payload.get("schedule"),
            payload.get("cut_off"),
            payload.get("business_context"),
            payload.get("bcbs239_output_mapping"),
            payload.get("cde_linkage"),
            payload.get("inputs"),
            payload.get("outputs"),
            payload.get("recipients"),
            payload.get("dependencies"),
            payload.get("spof_indicator", "No"),
            payload.get("supports_material_report", "No"),
            payload.get("supports_material_kri", "No"),
            payload.get("supports_material_model", "No"),
            payload.get("used_by_multiple_bus", "No"),
            payload.get("number_active_users"),
            payload.get("created_by_bu", "Yes"),
            payload.get("acquired_third_party", "No"),
            payload.get("support_contract_sla", "No"),
            payload.get("library_of_controls"),
            payload.get("last_risk_assessment"),
            payload.get("exceptions_remediation_actions"),
            payload.get("industrialization_decommissioning_status"),
            material,
            payload.get("materiality_rationale"),
            payload.get("inherent_risk", "Medium"),
            payload.get("residual_risk", "Medium"),
            payload.get("overall_status", "Registered"),
            "Not Checked",
            payload.get("lifecycle_status", "Registered"),
            payload.get("next_review_date"),
            payload.get("industrialization_rationale"),
            payload.get("decommissioning_rationale"),
            username,
            now,
            now,
            payload.get("mapping_na_justification"),
        ),
    )
    insert_audit("EUC", euc_id, "CREATE", username, None, {"reference_id": reference_id, "name": payload.get("name")})
    create_task(
        euc_id=euc_id,
        task_type="Risk assessment",
        title=f"Complete policy risk assessment for {reference_id}",
        description="Risk assessment task generated after EUC Inventory registration.",
        assigned_to=payload.get("owner"),
        assigned_role=OWNER_ROLE,
        due_date=add_days(DEFAULT_DUE_DAYS["Risk assessment"]),
        priority="High",
        username=username,
    )
    create_task(
        euc_id=euc_id,
        task_type="Document submission",
        title=f"Submit mandatory documentation for {reference_id}",
        description="Upload initial evidence pack in line with residual risk and lifecycle stage.",
        assigned_to=payload.get("owner"),
        assigned_role=OWNER_ROLE,
        due_date=add_days(DEFAULT_DUE_DAYS["Document submission"]),
        priority="Medium",
        username=username,
    )
    return euc_id

def update_euc(euc_id: int, payload: dict[str, Any], username: str) -> None:
    old = get_euc(euc_id)
    if not old:
        raise ValueError("EUC not found")
    errors = validate_mapping_fields(payload)
    if errors:
        raise ValueError("\n".join(errors))
    allowed_fields = [
        "name",
        "description",
        "purpose",
        "legal_entity",
        "owner",
        "owner_delegate",
        "reviewer",
        "business_unit",
        "technology_type",
        "storage_location",
        "frequency",
        "schedule",
        "cut_off",
        "business_context",
        "bcbs239_output_mapping",
        "cde_linkage",
        "inputs",
        "outputs",
        "recipients",
        "dependencies",
        "spof_indicator",
        "supports_material_report",
        "supports_material_kri",
        "supports_material_model",
        "used_by_multiple_bus",
        "number_active_users",
        "created_by_bu",
        "acquired_third_party",
        "support_contract_sla",
        "library_of_controls",
        "last_risk_assessment",
        "exceptions_remediation_actions",
        "industrialization_decommissioning_status",
        "materiality_rationale",
        "overall_status",
        "lifecycle_status",
        "next_review_date",
        "industrialization_rationale",
        "decommissioning_rationale",
        "mapping_na_justification",
    ]
    payload = dict(payload)
    payload["materially_supports_bcbs239"] = material_supports_bcbs239(
        payload.get("supports_material_report", old.get("supports_material_report")),
        payload.get("supports_material_kri", old.get("supports_material_kri")),
        payload.get("supports_material_model", old.get("supports_material_model")),
    )
    allowed_fields.append("materially_supports_bcbs239")
    assignments = ", ".join([f"{field} = ?" for field in allowed_fields])
    values = [payload.get(field, old.get(field)) for field in allowed_fields]
    values.extend([utc_now(), euc_id])
    execute(f"UPDATE eucs SET {assignments}, updated_at = ? WHERE euc_id = ?", tuple(values))
    insert_audit("EUC", euc_id, "UPDATE", username, old, payload)


def update_euc_status(euc_id: int, lifecycle_status: str, username: str, overall_status: str | None = None) -> None:
    old = get_euc(euc_id)
    execute(
        "UPDATE eucs SET lifecycle_status = ?, overall_status = ?, updated_at = ? WHERE euc_id = ?",
        (lifecycle_status, overall_status or lifecycle_status, utc_now(), euc_id),
    )
    insert_audit("EUC", euc_id, "STATUS_TRANSITION", username, old, {"lifecycle_status": lifecycle_status})


def get_components(euc_id: int) -> pd.DataFrame:
    return dataframe(
        """
        SELECT c.*, e.reference_id, e.name AS euc_name
        FROM components c
        JOIN eucs e ON e.euc_id = c.euc_id
        WHERE c.euc_id = ?
        ORDER BY c.component_id
        """,
        (euc_id,),
    )


COMPONENT_FIELDS = [
    "euc_id",
    "component_name",
    "component_type",
    "technology",
    "business_unit",
    "euc_application",
    "material_report_mapping",
    "operationalization_document_link",
    "storage_location",
    "controlled_storage_type",
    "input_sources",
    "cut_off_times",
    "processing_schedule",
    "execution_frequency",
    "cde_mappings",
    "data_outputs",
    "level_of_automation",
    "backup_recovery_arrangements",
    "spof_risk",
    "modification_date",
    "review_date",
    "description",
    "criticality",
    "owner",
]


def create_component(payload: dict[str, Any], username: str) -> int:
    now = utc_now()
    component_id = execute(
        """
        INSERT INTO components(
            euc_id, component_name, component_type, technology, business_unit, euc_application,
            material_report_mapping, operationalization_document_link, storage_location, controlled_storage_type,
            input_sources, cut_off_times, processing_schedule, execution_frequency, cde_mappings, data_outputs,
            level_of_automation, backup_recovery_arrangements, spof_risk, modification_date, review_date,
            description, criticality, owner, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload["component_name"],
            payload["component_type"],
            payload.get("technology"),
            payload.get("business_unit"),
            payload.get("euc_application"),
            payload.get("material_report_mapping"),
            payload.get("operationalization_document_link"),
            payload.get("storage_location"),
            payload.get("controlled_storage_type"),
            payload.get("input_sources"),
            payload.get("cut_off_times"),
            payload.get("processing_schedule"),
            payload.get("execution_frequency"),
            payload.get("cde_mappings"),
            payload.get("data_outputs"),
            payload.get("level_of_automation"),
            payload.get("backup_recovery_arrangements"),
            payload.get("spof_risk"),
            payload.get("modification_date"),
            payload.get("review_date"),
            payload.get("description"),
            payload.get("criticality"),
            payload.get("owner"),
            now,
        ),
    )
    insert_audit("EUC Asset", component_id, "CREATE", username, None, payload)
    return component_id


def get_component(component_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT c.*, e.reference_id, e.name AS euc_name
        FROM components c
        JOIN eucs e ON e.euc_id = c.euc_id
        WHERE c.component_id = ?
        """,
        (component_id,),
    )


def update_component(component_id: int, payload: dict[str, Any], username: str) -> None:
    old = get_component(component_id)
    if not old:
        raise ValueError("EUC asset was not found.")
    if not str(payload.get("component_name", "")).strip():
        raise ValueError("Files / Asset name is required.")
    allowed = [field for field in COMPONENT_FIELDS if field != "euc_id"]
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [payload.get(field, old.get(field)) for field in allowed]
    values.append(component_id)
    execute(f"UPDATE components SET {assignments} WHERE component_id = ?", tuple(values))
    insert_audit("EUC Asset", component_id, "UPDATE", username, old, payload)


def get_risk_assessments(euc_id: int) -> pd.DataFrame:
    return dataframe("SELECT * FROM risk_assessments WHERE euc_id = ? ORDER BY version DESC, assessment_id DESC", (euc_id,))


def get_risk_assessment(assessment_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT ra.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit
        FROM risk_assessments ra
        JOIN eucs e ON e.euc_id = ra.euc_id
        WHERE ra.assessment_id = ?
        """,
        (assessment_id,),
    )


def create_risk_assessment(payload: dict[str, Any], username: str) -> int:
    """Create a policy-style risk assessment aligned to the uploaded workbook.

    The previous MVP accepted five numeric sliders. This function still accepts that
    payload as a fallback, but the primary path now follows the workbook logic:
    materiality questions -> effective inherent risk -> baseline controls -> residual matrix.
    """
    calculation = calculate_policy_risk(payload)
    controls_payload = payload.get("controls") or {}
    control_rows = []
    for control in BASELINE_CONTROL_AREAS:
        value = controls_payload.get(control, {}) if isinstance(controls_payload, dict) else {}
        if isinstance(value, dict):
            status = value.get("status") or calculation["control_statuses"].get(control)
            rationale = value.get("rationale")
        else:
            status = value or calculation["control_statuses"].get(control)
            rationale = None
        if status == "N/A" and control not in NA_ALLOWED_CONTROL_KEYS:
            raise ValueError(f"N/A is not permitted for control: {control}")
        control_rows.append(
            {
                "control_area": control,
                "status": status,
                "meaning": CONTROL_DEFAULT_MEANINGS.get(control),
                "rationale": rationale,
            }
        )

    row = fetch_one("SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM risk_assessments WHERE euc_id = ?", (payload["euc_id"],))
    version = int(row["next_version"])
    now = utc_now()
    assessment_id = execute(
        """
        INSERT INTO risk_assessments(
            euc_id, assessment_date, assessed_by, assessment_type, materiality_q1, materiality_q2, materiality_q3,
            materially_supports_bcbs239, owner_integrity_level, owner_timeliness_level, effective_integrity_level,
            effective_timeliness_level, integrity_control_effectiveness, timeliness_control_effectiveness,
            integrity_residual_level, timeliness_residual_level, integrity_rationale, timeliness_rationale,
            control_assessment_json, required_action_guidance, integrity_accuracy_score, timeliness_availability_score,
            complexity_score, business_criticality_score, control_effectiveness_score, inherent_risk, residual_risk,
            rationale, trigger_type, version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload.get("assessment_date", date.today().isoformat()),
            payload.get("assessed_by", username),
            payload.get("assessment_type") or payload.get("trigger_type", "Manual trigger"),
            payload.get("materiality_q1", "No"),
            payload.get("materiality_q2", "No"),
            payload.get("materiality_q3", "No"),
            calculation["materially_supports_bcbs239"],
            calculation["owner_integrity_level"],
            calculation["owner_timeliness_level"],
            calculation["effective_integrity_level"],
            calculation["effective_timeliness_level"],
            calculation["integrity_control_effectiveness"],
            calculation["timeliness_control_effectiveness"],
            calculation["integrity_residual_level"],
            calculation["timeliness_residual_level"],
            payload.get("integrity_rationale"),
            payload.get("timeliness_rationale"),
            json.dumps(control_rows, ensure_ascii=False),
            calculation["required_action_guidance"],
            risk_rank(calculation["effective_integrity_level"]),
            risk_rank(calculation["effective_timeliness_level"]),
            risk_rank(calculation["inherent_risk"]),
            risk_rank(calculation["inherent_risk"]),
            max(CONTROL_EFFECTIVENESS_RANK.get(calculation["integrity_control_effectiveness"], 2), CONTROL_EFFECTIVENESS_RANK.get(calculation["timeliness_control_effectiveness"], 2)),
            calculation["inherent_risk"],
            calculation["residual_risk"],
            payload.get("rationale"),
            payload.get("trigger_type") or payload.get("assessment_type", "Manual trigger"),
            version,
            now,
        ),
    )
    lifecycle = "Awaiting Documentation" if calculation["residual_risk"] in {"Low", "Medium", "High", "Very High"} else "Registered"
    execute(
        """
        UPDATE eucs
        SET inherent_risk = ?, residual_risk = ?, materially_supports_bcbs239 = ?, lifecycle_status = ?, overall_status = ?,
            last_risk_assessment = ?, updated_at = ?
        WHERE euc_id = ?
        """,
        (
            calculation["inherent_risk"],
            calculation["residual_risk"],
            calculation["materially_supports_bcbs239"],
            lifecycle,
            lifecycle,
            payload.get("assessment_date", date.today().isoformat()),
            utc_now(),
            payload["euc_id"],
        ),
    )
    insert_audit("Risk Assessment", assessment_id, "CREATE", username, None, {**payload, **calculation})
    evaluate_and_update_completeness(payload["euc_id"], username, create_missing_tasks=True)
    return assessment_id


DELETE_ENTITY_CONFIG = {
    "EUC": {"table": "eucs", "pk": "euc_id", "euc_fk": "euc_id"},
    "EUC Asset": {"table": "components", "pk": "component_id", "euc_fk": "euc_id"},
    "Risk Assessment": {"table": "risk_assessments", "pk": "assessment_id", "euc_fk": "euc_id"},
    "Document": {"table": "documents", "pk": "document_id", "euc_fk": "euc_id"},
    "Task": {"table": "tasks", "pk": "task_id", "euc_fk": "euc_id"},
    "Finding": {"table": "findings", "pk": "finding_id", "euc_fk": "euc_id"},
    "Review": {"table": "reviews", "pk": "review_id", "euc_fk": "euc_id"},
    "Exception": {"table": "exceptions", "pk": "exception_id", "euc_fk": "euc_id"},
    "Incident": {"table": "incidents", "pk": "incident_id", "euc_fk": "euc_id"},
    "Material Change": {"table": "material_changes", "pk": "change_id", "euc_fk": "euc_id"},
    "Required Artifact Rule": {"table": "required_artifact_rules", "pk": "rule_id", "euc_fk": None},
    "Reference Data": {"table": "reference_data", "pk": "ref_id", "euc_fk": None},
    "Due-date Rule": {"table": "due_date_rules", "pk": "rule_id", "euc_fk": None},
    "User Profile": {"table": "user_profiles", "pk": "user_id", "euc_fk": None},
}


def _delete_document_file(old: dict[str, Any]) -> None:
    file_path = old.get("file_path") if old else None
    if not file_path:
        return
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        if path.exists() and path.is_file():
            path.unlink()
    except OSError:
        # Deletion of the DB record must not fail because a local demo file is
        # already missing or locked. The row snapshot remains in the audit trail.
        pass


def _refresh_euc_after_assessment_delete(euc_id: int, username: str) -> None:
    latest = fetch_one(
        """
        SELECT inherent_risk, residual_risk, materially_supports_bcbs239, assessment_date
        FROM risk_assessments
        WHERE euc_id = ?
        ORDER BY version DESC, assessment_id DESC
        LIMIT 1
        """,
        (euc_id,),
    )
    if latest:
        execute(
            """
            UPDATE eucs
            SET inherent_risk = ?, residual_risk = ?, materially_supports_bcbs239 = ?, last_risk_assessment = ?, updated_at = ?
            WHERE euc_id = ?
            """,
            (
                latest.get("inherent_risk"),
                latest.get("residual_risk"),
                latest.get("materially_supports_bcbs239"),
                latest.get("assessment_date"),
                utc_now(),
                euc_id,
            ),
        )
    else:
        execute(
            """
            UPDATE eucs
            SET inherent_risk = 'Medium', residual_risk = 'Medium', materially_supports_bcbs239 = 'No',
                last_risk_assessment = NULL, documentation_completeness_status = 'Incomplete', updated_at = ?
            WHERE euc_id = ?
            """,
            (utc_now(), euc_id),
        )
    evaluate_and_update_completeness(euc_id, username, create_missing_tasks=False)


def delete_record(entity_type: str, entity_id: int | str, username: str, role: str) -> None:
    """Delete one MVP record with audit trail. Restricted to GCC and IT Governance Admin."""
    if not can_delete_records(role):
        raise PermissionError("Only GCC and Group IT Governance Administrator can delete records.")
    if entity_type not in DELETE_ENTITY_CONFIG:
        raise ValueError(f"Unsupported delete entity type: {entity_type}")
    cfg = DELETE_ENTITY_CONFIG[entity_type]
    table = cfg["table"]
    pk = cfg["pk"]
    old = fetch_one(f"SELECT * FROM {table} WHERE {pk} = ?", (entity_id,))
    if not old:
        raise ValueError(f"{entity_type} {entity_id} was not found.")
    euc_id = old.get(cfg.get("euc_fk")) if cfg.get("euc_fk") else None

    if entity_type == "EUC":
        # Child rows are deleted explicitly because the MVP schema uses normal
        # foreign keys rather than ON DELETE CASCADE. Audit the EUC snapshot as
        # the governed deletion record, and keep audit_trail immutable.
        for doc in fetch_all("SELECT * FROM documents WHERE euc_id = ?", (entity_id,)):
            _delete_document_file(doc)
        for child_table in [
            "components",
            "risk_assessments",
            "tasks",
            "findings",
            "reviews",
            "exceptions",
            "incidents",
            "material_changes",
            "documents",
        ]:
            execute(f"DELETE FROM {child_table} WHERE euc_id = ?", (entity_id,))
        execute("DELETE FROM eucs WHERE euc_id = ?", (entity_id,))
        insert_audit(entity_type, entity_id, "DELETE", username, old, None)
        return

    if entity_type == "Document":
        _delete_document_file(old)
        execute("UPDATE tasks SET closure_evidence_document_id = NULL WHERE closure_evidence_document_id = ?", (entity_id,))
        execute("UPDATE exceptions SET closure_evidence_document_id = NULL WHERE closure_evidence_document_id = ?", (entity_id,))

    if entity_type == "Review":
        execute("UPDATE findings SET review_id = NULL WHERE review_id = ?", (entity_id,))

    execute(f"DELETE FROM {table} WHERE {pk} = ?", (entity_id,))
    insert_audit(entity_type, entity_id, "DELETE", username, old, None)

    if entity_type == "Risk Assessment" and euc_id:
        _refresh_euc_after_assessment_delete(int(euc_id), username)
    elif entity_type == "Document" and euc_id:
        evaluate_and_update_completeness(int(euc_id), username, create_missing_tasks=False)


def safe_filename(filename: str) -> str:
    stem = Path(filename).stem[:80]
    suffix = Path(filename).suffix[:20]
    clean_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "document"
    return f"{clean_stem}{suffix}"


def save_document_file(euc_id: int, original_name: str, file_bytes: bytes) -> tuple[str, str]:
    euc_folder = UPLOAD_PATH / f"euc_{euc_id}"
    euc_folder.mkdir(parents=True, exist_ok=True)
    file_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_filename(original_name)}"
    file_path = euc_folder / file_name
    with open(file_path, "wb") as fh:
        fh.write(file_bytes)
    return file_name, str(file_path.relative_to(UPLOAD_PATH.parent))


def create_document_record(payload: dict[str, Any], username: str) -> int:
    now = utc_now()
    document_id = execute(
        """
        INSERT INTO documents(
            euc_id, file_name, file_path, document_type, requirement, control_area, cacrt_dimension,
            risk_applicability, lifecycle_stage, version, status, uploaded_by, uploaded_at, reviewed_by,
            reviewed_at, comments, deficiency_tag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload["file_name"],
            payload["file_path"],
            payload["document_type"],
            payload.get("requirement"),
            payload.get("control_area"),
            payload.get("cacrt_dimension"),
            payload.get("risk_applicability"),
            payload.get("lifecycle_stage"),
            payload.get("version"),
            payload.get("status", "Submitted"),
            username,
            now,
            payload.get("reviewed_by"),
            payload.get("reviewed_at"),
            payload.get("comments"),
            payload.get("deficiency_tag"),
        ),
    )
    insert_audit("Document", document_id, "UPLOAD", username, None, payload)
    evaluate_and_update_completeness(payload["euc_id"], username, create_missing_tasks=False)
    return document_id


def get_documents(euc_id: int | None = None) -> pd.DataFrame:
    if euc_id:
        return dataframe("SELECT * FROM documents WHERE euc_id = ? ORDER BY uploaded_at DESC", (euc_id,))
    return dataframe("SELECT * FROM documents ORDER BY uploaded_at DESC")


def review_document(document_id: int, status: str, comments: str, deficiency_tag: str, username: str) -> None:
    old = fetch_one("SELECT * FROM documents WHERE document_id = ?", (document_id,))
    if not old:
        raise ValueError("Document not found")
    execute(
        """
        UPDATE documents
        SET status = ?, comments = ?, deficiency_tag = ?, reviewed_by = ?, reviewed_at = ?
        WHERE document_id = ?
        """,
        (status, comments, deficiency_tag, username, utc_now(), document_id),
    )
    action = "ACCEPT" if status == "Accepted" else "REJECT" if status == "Rejected" else "REVIEW"
    insert_audit("Document", document_id, action, username, old, {"status": status, "comments": comments, "deficiency_tag": deficiency_tag})
    if status == "Rejected":
        create_task(
            euc_id=old["euc_id"],
            task_type="Missing evidence",
            title=f"Replace rejected {old['document_type']} evidence",
            description=comments or "Evidence was rejected during review and must be remediated.",
            assigned_to=get_euc(old["euc_id"]).get("owner"),
            assigned_role=OWNER_ROLE,
            due_date=add_days(DEFAULT_DUE_DAYS["Missing evidence"]),
            priority="High",
            username=username,
        )
    evaluate_and_update_completeness(old["euc_id"], username, create_missing_tasks=True)


def seed_required_rules(username: str = "system") -> None:
    existing = fetch_one("SELECT COUNT(*) AS n FROM required_artifact_rules")
    if existing and int(existing["n"]) > 0:
        return
    for risk, docs in DEFAULT_REQUIRED_ARTIFACTS.items():
        for doc_type in docs:
            execute(
                """
                INSERT INTO required_artifact_rules(
                    risk_level, lifecycle_stage, required_document_type, control_area, cacrt_dimension,
                    mandatory_flag, maker_checker_comments, proposed_by, approved_by, approval_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    risk,
                    "Active",
                    doc_type,
                    "Reconciliation & Controls" if "Reconciliation" in doc_type else "Ownership & Accountability",
                    "Completeness",
                    1,
                    "Default MVP rule loaded during initialization.",
                    username,
                    username,
                    "Approved",
                ),
            )


def required_documents_for_euc(euc_id: int) -> pd.DataFrame:
    euc = get_euc(euc_id)
    if not euc:
        return pd.DataFrame()
    risk = euc.get("residual_risk") or "Medium"
    rules = dataframe(
        """
        SELECT * FROM required_artifact_rules
        WHERE risk_level = ? AND mandatory_flag = 1 AND approval_status = 'Approved'
        ORDER BY required_document_type
        """,
        (risk,),
    )
    if rules.empty:
        rows = [
            {
                "risk_level": risk,
                "lifecycle_stage": euc.get("lifecycle_status"),
                "required_document_type": doc,
                "control_area": None,
                "cacrt_dimension": None,
                "mandatory_flag": 1,
            }
            for doc in DEFAULT_REQUIRED_ARTIFACTS.get(risk, [])
        ]
        return pd.DataFrame(rows)
    return rules


def artifact_checklist(euc_id: int) -> pd.DataFrame:
    required = required_documents_for_euc(euc_id)
    docs = get_documents(euc_id)
    rows: list[dict[str, Any]] = []
    latest_assessment = fetch_one(
        """
        SELECT assessment_id, version, assessment_date, assessed_by, inherent_risk, residual_risk
        FROM risk_assessments
        WHERE euc_id = ?
        ORDER BY version DESC, assessment_id DESC
        LIMIT 1
        """,
        (euc_id,),
    )
    for _, req in required.iterrows():
        doc_type = req["required_document_type"]
        if doc_type == "Risk Assessment":
            if latest_assessment:
                status = "Accepted"
                document_id = None
                reviewed_by = latest_assessment.get("assessed_by")
                comments = (
                    f"Satisfied by Risk Assessment #{latest_assessment['assessment_id']} "
                    f"v{latest_assessment['version']} dated {latest_assessment['assessment_date']} "
                    f"({latest_assessment['inherent_risk']} inherent / {latest_assessment['residual_risk']} residual)."
                )
            else:
                status = "Missing"
                document_id = None
                reviewed_by = None
                comments = "No risk assessment exists for this EUC. Complete the Risk Assessment page; do not upload a risk assessment document."
        else:
            matching = docs[docs["document_type"] == doc_type] if not docs.empty else pd.DataFrame()
            if matching.empty:
                status = "Missing"
                document_id = None
                reviewed_by = None
                comments = None
            else:
                status_priority = {"Accepted": 1, "Submitted": 2, "Rejected": 3, "Expired": 4, "Pending": 5, "Missing": 6, "Superseded": 7}
                matching = matching.copy()
                matching["_rank"] = matching["status"].map(status_priority).fillna(99)
                best = matching.sort_values(["_rank", "uploaded_at"]).iloc[0]
                status = best["status"]
                document_id = int(best["document_id"])
                reviewed_by = best.get("reviewed_by")
                comments = best.get("comments")
        rows.append(
            {
                "document_type": doc_type,
                "mandatory": bool(req.get("mandatory_flag", 1)),
                "control_area": req.get("control_area"),
                "cacrt_dimension": req.get("cacrt_dimension"),
                "status": status,
                "document_id": document_id,
                "reviewed_by": reviewed_by,
                "comments": comments,
            }
        )
    return pd.DataFrame(rows)

def evaluate_and_update_completeness(euc_id: int, username: str, create_missing_tasks: bool = False) -> str:
    checklist = artifact_checklist(euc_id)
    if checklist.empty:
        status = "No Rules"
    elif (checklist["status"] == "Accepted").all():
        status = "Complete"
    elif checklist["status"].isin(["Missing", "Rejected", "Expired"]).any():
        status = "Incomplete"
    else:
        status = "Submitted - Pending Review"
    execute(
        "UPDATE eucs SET documentation_completeness_status = ?, updated_at = ? WHERE euc_id = ?",
        (status, utc_now(), euc_id),
    )
    if create_missing_tasks and not checklist.empty:
        euc = get_euc(euc_id)
        for _, row in checklist[checklist["status"].isin(["Missing", "Rejected", "Expired"])].iterrows():
            if row["document_type"] == "Risk Assessment":
                task_type = "Risk assessment"
                title = "Complete mandatory Risk Assessment"
                description = "Generated by required artifact checklist. Complete the Risk Assessment page; do not upload a risk assessment document."
                due_days = DEFAULT_DUE_DAYS["Risk assessment"]
            else:
                task_type = "Missing evidence"
                title = f"Provide mandatory {row['document_type']}"
                description = "Generated by required artifact checklist. Override requires an approved exception."
                due_days = DEFAULT_DUE_DAYS["Missing evidence"]
            existing = fetch_one(
                """
                SELECT task_id FROM tasks
                WHERE euc_id = ? AND task_type = ? AND title = ? AND status IN ('Open','In Progress','Blocked')
                """,
                (euc_id, task_type, title),
            )
            if not existing:
                create_task(
                    euc_id=euc_id,
                    task_type=task_type,
                    title=title,
                    description=description,
                    assigned_to=euc.get("owner") if euc else None,
                    assigned_role=OWNER_ROLE,
                    due_date=add_days(due_days),
                    priority="High" if euc and euc.get("residual_risk") in {"High", "Very High"} else "Medium",
                    username=username,
                )
    return status


def create_task(
    euc_id: int | None,
    task_type: str,
    title: str,
    description: str | None,
    assigned_to: str | None,
    assigned_role: str | None,
    due_date: str | None,
    priority: str,
    username: str,
    status: str = "Open",
) -> int:
    task_id = execute(
        """
        INSERT INTO tasks(euc_id, task_type, title, description, assigned_to, assigned_role, due_date, status, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (euc_id, task_type, title, description, assigned_to, assigned_role, due_date, status, priority, utc_now()),
    )
    insert_audit("Task", task_id, "CREATE", username, None, {"title": title, "assigned_to": assigned_to, "assigned_role": assigned_role})
    return task_id


def get_tasks(
    role: str | None = None,
    username: str | None = None,
    open_only: bool = False,
    euc_id: int | None = None,
) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if open_only:
        where.append("t.status IN ('Open','In Progress','Blocked','Closure Requested')")
    if euc_id:
        where.append("t.euc_id = ?")
        params.append(int(euc_id))
    if role and username and not can_view_all(role):
        where.append("(t.assigned_to = ? OR t.assigned_role = ?)")
        params.extend([username, role])
    elif role == APPROVER_ROLE:
        where.append("(t.assigned_role = ? OR t.assigned_to = ?)")
        params.extend([role, username])
    sql = """
        SELECT t.*, e.reference_id, e.name AS euc_name, e.owner, e.residual_risk,
               up.full_name AS assigned_full_name, up.email AS assigned_email,
               CASE WHEN t.due_date IS NOT NULL AND date(t.due_date) < date('now') AND t.status NOT IN ('Closed','Cancelled') THEN 1 ELSE 0 END AS overdue
        FROM tasks t
        LEFT JOIN eucs e ON e.euc_id = t.euc_id
        LEFT JOIN user_profiles up ON up.username = t.assigned_to
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY overdue DESC, date(t.due_date), t.priority DESC"
    return dataframe(sql, tuple(params))


def update_task(task_id: int, status: str, closure_reason: str | None, evidence_document_id: int | None, username: str) -> None:
    old = fetch_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    if not old:
        raise ValueError("Task not found")
    closed_at = utc_now() if status in {"Closed", "Cancelled"} else None
    execute(
        """
        UPDATE tasks
        SET status = ?, closure_reason = ?, closure_evidence_document_id = ?, closed_at = ?
        WHERE task_id = ?
        """,
        (status, closure_reason, evidence_document_id, closed_at, task_id),
    )
    insert_audit("Task", task_id, "UPDATE", username, old, {"status": status, "closure_reason": closure_reason})


def create_review(payload: dict[str, Any], username: str, role: str) -> int:
    euc = get_euc(payload["euc_id"])
    if not euc:
        raise ValueError("EUC not found")
    if username == euc.get("owner") and role in {DVU_ROLE, GCC_ROLE}:
        raise ValueError("Independent reviewer cannot be the EUC Owner for the same EUC.")
    review_id = execute(
        """
        INSERT INTO reviews(euc_id, reviewer, reviewer_role, review_type, outcome, comments, review_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            username,
            role,
            payload.get("review_type", "Data Validation"),
            payload["outcome"],
            payload.get("comments"),
            date.today().isoformat(),
        ),
    )
    insert_audit("Review", review_id, "CREATE", username, None, payload)
    outcome = payload["outcome"]
    if outcome == "Accepted":
        update_euc_status(payload["euc_id"], "Active", username, "Active")
    elif outcome in {"Accepted with comments", "Returned for remediation", "Finding raised"}:
        update_euc_status(payload["euc_id"], "Under Remediation", username, "Under remediation")
        create_task(
            euc_id=payload["euc_id"],
            task_type="Review response",
            title=f"Respond to {payload.get('review_type', 'review')} outcome",
            description=payload.get("comments"),
            assigned_to=euc.get("owner"),
            assigned_role=OWNER_ROLE,
            due_date=add_days(DEFAULT_DUE_DAYS["Review response"]),
            priority="High",
            username=username,
        )
    return review_id


def get_reviews(euc_id: int | None = None) -> pd.DataFrame:
    if euc_id:
        return dataframe("SELECT * FROM reviews WHERE euc_id = ? ORDER BY review_date DESC, review_id DESC", (euc_id,))
    return dataframe("SELECT r.*, e.reference_id, e.name AS euc_name FROM reviews r JOIN eucs e ON e.euc_id = r.euc_id ORDER BY review_date DESC")


def create_finding(payload: dict[str, Any], username: str) -> int:
    now = utc_now()
    finding_id = execute(
        """
        INSERT INTO findings(
            euc_id, review_id, severity, requirement, control_area, finding_description,
            remediation_required, assigned_to, due_date, status, closure_comments, created_by, created_at, closed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload.get("review_id"),
            payload["severity"],
            payload.get("requirement"),
            payload.get("control_area"),
            payload["finding_description"],
            payload.get("remediation_required"),
            payload.get("assigned_to"),
            payload.get("due_date"),
            payload.get("status", "Open"),
            payload.get("closure_comments"),
            username,
            now,
            None,
        ),
    )
    insert_audit("Finding", finding_id, "CREATE", username, None, payload)
    euc = get_euc(payload["euc_id"])
    update_euc_status(payload["euc_id"], "Under Remediation", username, "Under remediation")
    create_task(
        euc_id=payload["euc_id"],
        task_type="Remediation",
        title=f"Remediate finding {finding_id}: {payload['severity']}",
        description=payload.get("remediation_required") or payload["finding_description"],
        assigned_to=payload.get("assigned_to") or (euc.get("owner") if euc else None),
        assigned_role=OWNER_ROLE,
        due_date=payload.get("due_date") or add_days(DEFAULT_DUE_DAYS["Remediation"]),
        priority="Critical" if payload["severity"] == "Critical" else "High",
        username=username,
    )
    return finding_id


def get_findings(euc_id: int | None = None, open_only: bool = False) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if euc_id:
        where.append("f.euc_id = ?")
        params.append(euc_id)
    if open_only:
        where.append("f.status NOT IN ('Closed','Cancelled')")
    sql = """
        SELECT f.*, e.reference_id, e.name AS euc_name, e.owner
        FROM findings f JOIN eucs e ON e.euc_id = f.euc_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE f.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, date(f.due_date)"
    return dataframe(sql, tuple(params))


def update_finding(finding_id: int, status: str, closure_comments: str, username: str) -> None:
    old = fetch_one("SELECT * FROM findings WHERE finding_id = ?", (finding_id,))
    if not old:
        raise ValueError("Finding not found")
    closed_at = utc_now() if status == "Closed" else None
    execute(
        "UPDATE findings SET status = ?, closure_comments = ?, closed_at = ? WHERE finding_id = ?",
        (status, closure_comments, closed_at, finding_id),
    )
    insert_audit("Finding", finding_id, "UPDATE", username, old, {"status": status, "closure_comments": closure_comments})


def get_exceptions(euc_id: int | None = None, open_only: bool = False) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if euc_id:
        where.append("x.euc_id = ?")
        params.append(euc_id)
    if open_only:
        where.append("x.status NOT IN ('Closed','Withdrawn')")
    sql = """
        SELECT x.*, e.reference_id, e.name AS euc_name, e.owner,
               CAST(julianday('now') - julianday(x.created_at) AS INTEGER) AS ageing_days,
               CASE WHEN x.expiry_date IS NOT NULL AND date(x.expiry_date) < date('now') THEN 1 ELSE 0 END AS expired
        FROM exceptions x JOIN eucs e ON e.euc_id = x.euc_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY expired DESC, date(x.expiry_date)"
    return dataframe(sql, tuple(params))


def create_exception(payload: dict[str, Any], username: str) -> int:
    exception_id = execute(
        """
        INSERT INTO exceptions(
            euc_id, control_gap, root_cause, compensating_controls, residual_risk, remediation_plan,
            target_date, expiry_date, approval_status, approved_by, status, created_at, closure_evidence_document_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload["control_gap"],
            payload.get("root_cause"),
            payload.get("compensating_controls"),
            payload.get("residual_risk"),
            payload.get("remediation_plan"),
            payload.get("target_date"),
            payload.get("expiry_date"),
            payload.get("approval_status", "Pending"),
            payload.get("approved_by"),
            payload.get("status", "Open"),
            utc_now(),
            payload.get("closure_evidence_document_id"),
        ),
    )
    insert_audit("Exception", exception_id, "CREATE", username, None, payload)
    update_euc_status(payload["euc_id"], "Exception Active", username, "Exception active")
    create_task(
        euc_id=payload["euc_id"],
        task_type="Review response",
        title=f"Approve or reject exception {exception_id}",
        description=payload["control_gap"],
        assigned_to=None,
        assigned_role=APPROVER_ROLE,
        due_date=add_days(7),
        priority="High",
        username=username,
    )
    return exception_id


def approve_exception(exception_id: int, approval_status: str, approved_by: str) -> None:
    old = fetch_one("SELECT * FROM exceptions WHERE exception_id = ?", (exception_id,))
    if not old:
        raise ValueError("Exception not found")
    status = "Open" if approval_status == "Approved" else "Rejected"
    execute(
        "UPDATE exceptions SET approval_status = ?, approved_by = ?, status = ? WHERE exception_id = ?",
        (approval_status, approved_by, status, exception_id),
    )
    insert_audit("Exception", exception_id, "APPROVAL", approved_by, old, {"approval_status": approval_status})


def get_incidents(euc_id: int | None = None, open_only: bool = False) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if euc_id:
        where.append("i.euc_id = ?")
        params.append(euc_id)
    if open_only:
        where.append("i.status <> 'Closed'")
    sql = """
        SELECT i.*, e.reference_id, e.name AS euc_name, e.owner
        FROM incidents i JOIN eucs e ON e.euc_id = i.euc_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date(i.incident_date) DESC"
    return dataframe(sql, tuple(params))


def create_incident(payload: dict[str, Any], username: str) -> int:
    incident_id = execute(
        """
        INSERT INTO incidents(
            euc_id, affected_outputs, incident_date, impact_summary, containment_status,
            correction_status, rca_status, remediation_actions, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload.get("affected_outputs"),
            payload.get("incident_date", date.today().isoformat()),
            payload.get("impact_summary"),
            payload.get("containment_status"),
            payload.get("correction_status"),
            payload.get("rca_status"),
            payload.get("remediation_actions"),
            payload.get("status", "Open"),
            utc_now(),
        ),
    )
    insert_audit("Incident", incident_id, "CREATE", username, None, payload)
    euc = get_euc(payload["euc_id"])
    update_euc_status(payload["euc_id"], "Incident Open", username, "Incident open")
    create_task(payload["euc_id"], "Reassessment", f"Reassess EUC after incident {incident_id}", payload.get("impact_summary"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Reassessment"]), "High", username)
    create_task(payload["euc_id"], "Documentation refresh", f"Refresh documentation after incident {incident_id}", payload.get("remediation_actions"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Documentation refresh"]), "High", username)
    return incident_id


def get_material_changes(euc_id: int | None = None) -> pd.DataFrame:
    if euc_id:
        return dataframe("SELECT * FROM material_changes WHERE euc_id = ? ORDER BY created_at DESC", (euc_id,))
    return dataframe(
        """
        SELECT m.*, e.reference_id, e.name AS euc_name, e.owner
        FROM material_changes m JOIN eucs e ON e.euc_id = m.euc_id
        ORDER BY m.created_at DESC
        """
    )


def create_material_change(payload: dict[str, Any], username: str) -> int:
    change_id = execute(
        """
        INSERT INTO material_changes(
            euc_id, change_type, description, impact_assessment, reassessment_required,
            documentation_refresh_required, status, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload["change_type"],
            payload["description"],
            payload.get("impact_assessment"),
            int(bool(payload.get("reassessment_required"))),
            int(bool(payload.get("documentation_refresh_required"))),
            payload.get("status", "Open"),
            username,
            utc_now(),
        ),
    )
    insert_audit("Material Change", change_id, "CREATE", username, None, payload)
    euc = get_euc(payload["euc_id"])
    update_euc_status(payload["euc_id"], "Under Change", username, "Under change")
    if payload.get("reassessment_required"):
        create_task(payload["euc_id"], "Reassessment", f"Reassess EUC after material change {change_id}", payload.get("impact_assessment"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Reassessment"]), "High", username)
    if payload.get("documentation_refresh_required"):
        create_task(payload["euc_id"], "Documentation refresh", f"Refresh documentation after material change {change_id}", payload.get("description"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Documentation refresh"]), "Medium", username)
    return change_id


def data_validation_queue() -> pd.DataFrame:
    return dataframe(
        """
        SELECT euc_id, reference_id, name, owner, business_unit, residual_risk, documentation_completeness_status, lifecycle_status, next_review_date
        FROM eucs
        WHERE lifecycle_status IN ('Review Ready', 'Under Remediation')
           OR documentation_completeness_status IN ('Complete', 'Submitted - Pending Review')
        ORDER BY CASE residual_risk WHEN 'Very High' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, next_review_date
        """
    )


def gcc_monitoring_dataset() -> dict[str, pd.DataFrame]:
    return {
        "risk_distribution": dataframe("SELECT residual_risk, COUNT(*) AS count FROM eucs GROUP BY residual_risk"),
        "missing_documentation": dataframe("SELECT reference_id, name, owner, residual_risk, documentation_completeness_status FROM eucs WHERE documentation_completeness_status <> 'Complete'"),
        "overdue_tasks": get_tasks(open_only=True).query("overdue == 1") if not get_tasks(open_only=True).empty else pd.DataFrame(),
        "open_findings": get_findings(open_only=True),
        "open_exceptions": get_exceptions(open_only=True),
        "open_incidents": get_incidents(open_only=True),
        "high_risk": dataframe("SELECT reference_id, name, owner, business_unit, residual_risk, spof_indicator FROM eucs WHERE residual_risk IN ('High','Very High')"),
        "spof": dataframe("SELECT reference_id, name, owner, residual_risk, spof_indicator FROM eucs WHERE spof_indicator = 'Yes'"),
        "industrialization": dataframe("SELECT reference_id, name, owner, residual_risk, industrialization_rationale FROM eucs WHERE lifecycle_status = 'Industrialization Candidate'"),
        "decommissioning": dataframe("SELECT reference_id, name, owner, residual_risk, decommissioning_rationale FROM eucs WHERE lifecycle_status IN ('Decommissioned','Archived') OR overall_status = 'Decommissioned'"),
    }


def dashboard_metrics() -> dict[str, int]:
    values = fetch_one(
        """
        SELECT
            COUNT(*) AS total_eucs,
            SUM(CASE WHEN residual_risk IN ('High','Very High') THEN 1 ELSE 0 END) AS high_very_high,
            SUM(CASE WHEN lifecycle_status = 'Industrialization Candidate' THEN 1 ELSE 0 END) AS industrialization_candidates,
            SUM(CASE WHEN lifecycle_status = 'Decommissioned' THEN 1 ELSE 0 END) AS decommissioned
        FROM eucs
        """
    ) or {}
    tasks = fetch_one("SELECT COUNT(*) AS n FROM tasks WHERE status NOT IN ('Closed','Cancelled')") or {"n": 0}
    overdue_reviews = fetch_one("SELECT COUNT(*) AS n FROM eucs WHERE next_review_date IS NOT NULL AND date(next_review_date) < date('now')") or {"n": 0}
    findings = fetch_one("SELECT COUNT(*) AS n FROM findings WHERE status NOT IN ('Closed','Cancelled')") or {"n": 0}
    exceptions = fetch_one("SELECT COUNT(*) AS n FROM exceptions WHERE status NOT IN ('Closed','Withdrawn','Rejected')") or {"n": 0}
    incidents = fetch_one("SELECT COUNT(*) AS n FROM incidents WHERE status <> 'Closed'") or {"n": 0}
    missing = fetch_one("SELECT COUNT(*) AS n FROM eucs WHERE documentation_completeness_status <> 'Complete'") or {"n": 0}
    return {
        "Total EUCs": int(values.get("total_eucs") or 0),
        "Missing mandatory docs": int(missing.get("n") or 0),
        "Overdue reviews": int(overdue_reviews.get("n") or 0),
        "Open findings": int(findings.get("n") or 0),
        "Open remediation tasks": int(tasks.get("n") or 0),
        "Open exceptions": int(exceptions.get("n") or 0),
        "Open incidents": int(incidents.get("n") or 0),
        "High / Very High EUCs": int(values.get("high_very_high") or 0),
        "Industrialization candidates": int(values.get("industrialization_candidates") or 0),
        "Decommissioned EUCs": int(values.get("decommissioned") or 0),
    }


def chart_data() -> dict[str, pd.DataFrame]:
    return {
        "by_lifecycle": dataframe("SELECT lifecycle_status, COUNT(*) AS count FROM eucs GROUP BY lifecycle_status ORDER BY count DESC"),
        "by_risk": dataframe("SELECT residual_risk, COUNT(*) AS count FROM eucs GROUP BY residual_risk"),
        "by_business_unit": dataframe("SELECT business_unit, COUNT(*) AS count FROM eucs GROUP BY business_unit ORDER BY count DESC"),
        "tasks_by_status": dataframe("SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"),
    }


def report_table(filters: dict[str, Any]) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if filters.get("owner") and filters["owner"] != "All":
        where.append("e.owner = ?")
        params.append(filters["owner"])
    if filters.get("business_unit") and filters["business_unit"] != "All":
        where.append("e.business_unit = ?")
        params.append(filters["business_unit"])
    if filters.get("risk_level") and filters["risk_level"] != "All":
        where.append("e.residual_risk = ?")
        params.append(filters["risk_level"])
    if filters.get("status") and filters["status"] != "All":
        where.append("e.lifecycle_status = ?")
        params.append(filters["status"])
    if filters.get("output_mapping"):
        where.append("lower(e.bcbs239_output_mapping) LIKE lower(?)")
        params.append(f"%{filters['output_mapping']}%")
    if filters.get("control_area") and filters["control_area"] != "All":
        where.append("EXISTS (SELECT 1 FROM documents d WHERE d.euc_id = e.euc_id AND d.control_area = ?)")
        params.append(filters["control_area"])
    if filters.get("due_before"):
        where.append("EXISTS (SELECT 1 FROM tasks t WHERE t.euc_id = e.euc_id AND date(t.due_date) <= date(?))")
        params.append(filters["due_before"])
    sql = """
        SELECT e.reference_id, e.name, e.owner, e.business_unit, e.residual_risk, e.lifecycle_status,
               e.documentation_completeness_status, e.bcbs239_output_mapping, e.spof_indicator, e.next_review_date,
               COUNT(DISTINCT t.task_id) AS open_tasks,
               COUNT(DISTINCT f.finding_id) AS open_findings
        FROM eucs e
        LEFT JOIN tasks t ON t.euc_id = e.euc_id AND t.status NOT IN ('Closed','Cancelled')
        LEFT JOIN findings f ON f.euc_id = e.euc_id AND f.status NOT IN ('Closed','Cancelled')
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY e.euc_id ORDER BY e.residual_risk DESC, e.reference_id"
    return dataframe(sql, tuple(params))


def audit_trail(filters: dict[str, Any] | None = None) -> pd.DataFrame:
    filters = filters or {}
    where = []
    params: list[Any] = []
    if filters.get("entity_type"):
        where.append("entity_type = ?")
        params.append(filters["entity_type"])
    if filters.get("entity_id"):
        where.append("entity_id = ?")
        params.append(str(filters["entity_id"]))
    if filters.get("performed_by"):
        where.append("performed_by = ?")
        params.append(filters["performed_by"])
    if filters.get("from_date"):
        where.append("date(performed_at) >= date(?)")
        params.append(filters["from_date"])
    if filters.get("to_date"):
        where.append("date(performed_at) <= date(?)")
        params.append(filters["to_date"])
    sql = "SELECT * FROM audit_trail"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY performed_at DESC, audit_id DESC"
    return dataframe(sql, tuple(params))


def load_reference_data() -> dict[str, list[str]]:
    refs = dataframe("SELECT category, value FROM reference_data WHERE active_flag = 1 ORDER BY category, value")
    result = {"document_type": DOCUMENT_TYPES, "lifecycle_status": LIFECYCLE_STATUSES, "risk_level": RISK_LEVELS, "control_area": CONTROL_AREAS, "cacrt_dimension": CACRT_DIMENSIONS, "task_type": TASK_TYPES}
    if refs.empty:
        return result
    for category in refs["category"].unique():
        values = refs[refs["category"] == category]["value"].tolist()
        if values:
            result[category] = values
    return result


def upsert_reference_value(category: str, value: str, username: str, comments: str = "") -> None:
    execute(
        """
        INSERT OR IGNORE INTO reference_data(category, value, active_flag, maker_checker_comments, proposed_by, approved_by, approval_status)
        VALUES (?, ?, 1, ?, ?, ?, 'Approved')
        """,
        (category, value, comments, username, username),
    )
    insert_audit("Reference Data", f"{category}:{value}", "UPSERT", username, None, {"category": category, "value": value})


def upsert_required_rule(payload: dict[str, Any], username: str) -> int:
    rule_id = execute(
        """
        INSERT INTO required_artifact_rules(
            risk_level, lifecycle_stage, required_document_type, control_area, cacrt_dimension,
            mandatory_flag, maker_checker_comments, proposed_by, approved_by, approval_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["risk_level"],
            payload["lifecycle_stage"],
            payload["required_document_type"],
            payload.get("control_area"),
            payload.get("cacrt_dimension"),
            int(bool(payload.get("mandatory_flag", True))),
            payload.get("maker_checker_comments"),
            username,
            username,
            "Approved",
        ),
    )
    insert_audit("Required Artifact Rule", rule_id, "CREATE", username, None, payload)
    return rule_id


def required_rules_table() -> pd.DataFrame:
    return dataframe("SELECT * FROM required_artifact_rules ORDER BY risk_level, required_document_type")


def reference_data_table(category: str | None = None) -> pd.DataFrame:
    if category:
        return dataframe("SELECT * FROM reference_data WHERE category = ? ORDER BY category, value", (category,))
    return dataframe("SELECT * FROM reference_data ORDER BY category, value")


def due_date_rules_table() -> pd.DataFrame:
    return dataframe("SELECT * FROM due_date_rules ORDER BY task_type, risk_level")


def initialize_reference_data(username: str = "system") -> None:
    seed_user_profiles(username)
    seed_required_rules(username)
    constants = {
        "document_type": DOCUMENT_TYPES,
        "lifecycle_status": LIFECYCLE_STATUSES,
        "risk_level": RISK_LEVELS,
        "control_area": CONTROL_AREAS,
        "cacrt_dimension": CACRT_DIMENSIONS,
    }
    for category, values in constants.items():
        for value in values:
            execute(
                """
                INSERT OR IGNORE INTO reference_data(category, value, active_flag, maker_checker_comments, proposed_by, approved_by, approval_status)
                VALUES (?, ?, 1, 'Seeded MVP reference value.', ?, ?, 'Approved')
                """,
                (category, value, username, username),
            )
    for task_type, days in DEFAULT_DUE_DAYS.items():
        execute(
            """
            INSERT OR IGNORE INTO due_date_rules(task_type, risk_level, due_days, active_flag, maker_checker_comments, proposed_by, approved_by, approval_status)
            VALUES (?, 'Any', ?, 1, 'Seeded MVP due-date rule.', ?, ?, 'Approved')
            """,
            (task_type, days, username, username),
        )



# ---------------------------------------------------------------------------
# Record update helpers used by table-select/edit UI patterns.
# These functions intentionally keep updates explicit and write audit events.
# ---------------------------------------------------------------------------

def get_task(task_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM tasks WHERE task_id = ?", (int(task_id),))


def update_task_full(task_id: int, payload: dict[str, Any], username: str) -> None:
    old = get_task(int(task_id))
    if not old:
        raise ValueError("Task not found")
    allowed = ["task_type", "title", "description", "assigned_to", "assigned_role", "due_date", "status", "priority", "closure_reason", "closure_evidence_document_id"]
    if not str(payload.get("title", old.get("title") or "")).strip():
        raise ValueError("Task title is required.")
    status = payload.get("status", old.get("status"))
    closed_at = utc_now() if status in {"Closed", "Cancelled"} else None
    assignments = ", ".join([f"{field} = ?" for field in allowed]) + ", closed_at = ?"
    values = [payload.get(field, old.get(field)) for field in allowed] + [closed_at, int(task_id)]
    execute(f"UPDATE tasks SET {assignments} WHERE task_id = ?", tuple(values))
    insert_audit("Task", int(task_id), "UPDATE", username, old, {field: payload.get(field, old.get(field)) for field in allowed})


def update_document_metadata(document_id: int, payload: dict[str, Any], username: str, review_update: bool = False) -> None:
    old = fetch_one("SELECT * FROM documents WHERE document_id = ?", (int(document_id),))
    if not old:
        raise ValueError("Document not found")
    allowed = ["document_type", "comments", "deficiency_tag"]
    if review_update:
        allowed += ["status", "reviewed_by", "reviewed_at"]
    if not str(payload.get("document_type", old.get("document_type") or "")).strip():
        raise ValueError("Document type is required.")
    update_payload = dict(payload)
    if review_update:
        update_payload["reviewed_by"] = username
        update_payload["reviewed_at"] = utc_now()
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [update_payload.get(field, old.get(field)) for field in allowed] + [int(document_id)]
    execute(f"UPDATE documents SET {assignments} WHERE document_id = ?", tuple(values))
    action = "REVIEW" if review_update else "UPDATE"
    insert_audit("Document", int(document_id), action, username, old, {field: update_payload.get(field, old.get(field)) for field in allowed})
    evaluate_and_update_completeness(int(old["euc_id"]), username, create_missing_tasks=review_update)


def update_review(review_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM reviews WHERE review_id = ?", (int(review_id),))
    if not old:
        raise ValueError("Review not found")
    allowed = ["review_type", "outcome", "comments", "review_date"]
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [payload.get(field, old.get(field)) for field in allowed] + [int(review_id)]
    execute(f"UPDATE reviews SET {assignments} WHERE review_id = ?", tuple(values))
    insert_audit("Review", int(review_id), "UPDATE", username, old, {field: payload.get(field, old.get(field)) for field in allowed})


def update_finding_full(finding_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM findings WHERE finding_id = ?", (int(finding_id),))
    if not old:
        raise ValueError("Finding not found")
    if not str(payload.get("finding_description", old.get("finding_description") or "")).strip():
        raise ValueError("Finding description is required.")
    allowed = ["severity", "requirement", "control_area", "finding_description", "remediation_required", "assigned_to", "due_date", "status", "closure_comments"]
    status = payload.get("status", old.get("status"))
    closed_at = utc_now() if status == "Closed" else None
    assignments = ", ".join([f"{field} = ?" for field in allowed]) + ", closed_at = ?"
    values = [payload.get(field, old.get(field)) for field in allowed] + [closed_at, int(finding_id)]
    execute(f"UPDATE findings SET {assignments} WHERE finding_id = ?", tuple(values))
    insert_audit("Finding", int(finding_id), "UPDATE", username, old, {field: payload.get(field, old.get(field)) for field in allowed})


def update_exception_full(exception_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM exceptions WHERE exception_id = ?", (int(exception_id),))
    if not old:
        raise ValueError("Exception not found")
    if not str(payload.get("control_gap", old.get("control_gap") or "")).strip():
        raise ValueError("Control gap is required.")
    allowed = ["control_gap", "root_cause", "compensating_controls", "residual_risk", "remediation_plan", "target_date", "expiry_date", "approval_status", "approved_by", "status", "closure_evidence_document_id"]
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [payload.get(field, old.get(field)) for field in allowed] + [int(exception_id)]
    execute(f"UPDATE exceptions SET {assignments} WHERE exception_id = ?", tuple(values))
    insert_audit("Exception", int(exception_id), "UPDATE", username, old, {field: payload.get(field, old.get(field)) for field in allowed})


def update_incident(incident_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM incidents WHERE incident_id = ?", (int(incident_id),))
    if not old:
        raise ValueError("Incident not found")
    allowed = ["affected_outputs", "incident_date", "impact_summary", "containment_status", "correction_status", "rca_status", "remediation_actions", "status"]
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [payload.get(field, old.get(field)) for field in allowed] + [int(incident_id)]
    execute(f"UPDATE incidents SET {assignments} WHERE incident_id = ?", tuple(values))
    insert_audit("Incident", int(incident_id), "UPDATE", username, old, {field: payload.get(field, old.get(field)) for field in allowed})


def update_material_change(change_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM material_changes WHERE change_id = ?", (int(change_id),))
    if not old:
        raise ValueError("Material change not found")
    if not str(payload.get("description", old.get("description") or "")).strip():
        raise ValueError("Description is required.")
    allowed = ["change_type", "description", "impact_assessment", "reassessment_required", "documentation_refresh_required", "status"]
    update_payload = dict(payload)
    update_payload["reassessment_required"] = int(bool(update_payload.get("reassessment_required", old.get("reassessment_required"))))
    update_payload["documentation_refresh_required"] = int(bool(update_payload.get("documentation_refresh_required", old.get("documentation_refresh_required"))))
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [update_payload.get(field, old.get(field)) for field in allowed] + [int(change_id)]
    execute(f"UPDATE material_changes SET {assignments} WHERE change_id = ?", tuple(values))
    insert_audit("Material Change", int(change_id), "UPDATE", username, old, {field: update_payload.get(field, old.get(field)) for field in allowed})


def update_required_rule(rule_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM required_artifact_rules WHERE rule_id = ?", (int(rule_id),))
    if not old:
        raise ValueError("Required artifact rule not found")
    allowed = ["risk_level", "lifecycle_stage", "required_document_type", "control_area", "cacrt_dimension", "mandatory_flag", "maker_checker_comments", "approval_status", "approved_by"]
    update_payload = dict(payload)
    update_payload["mandatory_flag"] = int(bool(update_payload.get("mandatory_flag", old.get("mandatory_flag"))))
    if update_payload.get("approval_status") == "Approved" and not update_payload.get("approved_by"):
        update_payload["approved_by"] = username
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [update_payload.get(field, old.get(field)) for field in allowed] + [int(rule_id)]
    execute(f"UPDATE required_artifact_rules SET {assignments} WHERE rule_id = ?", tuple(values))
    insert_audit("Required Artifact Rule", int(rule_id), "UPDATE", username, old, {field: update_payload.get(field, old.get(field)) for field in allowed})


def update_reference_value(ref_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM reference_data WHERE ref_id = ?", (int(ref_id),))
    if not old:
        raise ValueError("Reference data row not found")
    if not str(payload.get("value", old.get("value") or "")).strip():
        raise ValueError("Reference value is required.")
    duplicate = fetch_one(
        "SELECT ref_id FROM reference_data WHERE category = ? AND value = ? AND ref_id <> ?",
        (payload.get("category", old.get("category")), payload.get("value", old.get("value")), int(ref_id)),
    )
    if duplicate:
        raise ValueError("A reference value with this category and value already exists.")
    allowed = ["category", "value", "active_flag", "maker_checker_comments", "approval_status", "approved_by"]
    update_payload = dict(payload)
    update_payload["active_flag"] = int(bool(update_payload.get("active_flag", old.get("active_flag"))))
    if update_payload.get("approval_status") == "Approved" and not update_payload.get("approved_by"):
        update_payload["approved_by"] = username
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [update_payload.get(field, old.get(field)) for field in allowed] + [int(ref_id)]
    execute(f"UPDATE reference_data SET {assignments} WHERE ref_id = ?", tuple(values))
    insert_audit("Reference Data", int(ref_id), "UPDATE", username, old, {field: update_payload.get(field, old.get(field)) for field in allowed})


def create_due_date_rule(payload: dict[str, Any], username: str) -> int:
    rule_id = execute(
        """
        INSERT INTO due_date_rules(task_type, risk_level, due_days, active_flag, maker_checker_comments, proposed_by, approved_by, approval_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["task_type"],
            payload.get("risk_level", "Any"),
            int(payload["due_days"]),
            int(bool(payload.get("active_flag", True))),
            payload.get("maker_checker_comments"),
            username,
            username if payload.get("approval_status", "Approved") == "Approved" else None,
            payload.get("approval_status", "Approved"),
        ),
    )
    insert_audit("Due-date Rule", rule_id, "CREATE", username, None, payload)
    return rule_id


def update_due_date_rule(rule_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM due_date_rules WHERE rule_id = ?", (int(rule_id),))
    if not old:
        raise ValueError("Due-date rule not found")
    allowed = ["task_type", "risk_level", "due_days", "active_flag", "maker_checker_comments", "approval_status", "approved_by"]
    update_payload = dict(payload)
    update_payload["due_days"] = int(update_payload.get("due_days", old.get("due_days")))
    update_payload["active_flag"] = int(bool(update_payload.get("active_flag", old.get("active_flag"))))
    if update_payload.get("approval_status") == "Approved" and not update_payload.get("approved_by"):
        update_payload["approved_by"] = username
    assignments = ", ".join([f"{field} = ?" for field in allowed])
    values = [update_payload.get(field, old.get(field)) for field in allowed] + [int(rule_id)]
    try:
        execute(f"UPDATE due_date_rules SET {assignments} WHERE rule_id = ?", tuple(values))
    except Exception as exc:
        raise ValueError("A due-date rule with this task type and risk level may already exist.") from exc
    insert_audit("Due-date Rule", int(rule_id), "UPDATE", username, old, {field: update_payload.get(field, old.get(field)) for field in allowed})


def close_open_obligations_for_decommissioning(euc_id: int, username: str) -> dict[str, int]:
    """Controlled decommissioning support: close non-audit records only through explicit status updates."""
    task_rows = fetch_all("SELECT task_id FROM tasks WHERE euc_id = ? AND status NOT IN ('Closed','Cancelled')", (euc_id,))
    finding_rows = fetch_all("SELECT finding_id FROM findings WHERE euc_id = ? AND status NOT IN ('Closed','Cancelled')", (euc_id,))
    for row in task_rows:
        update_task(row["task_id"], "Cancelled", "Closed as part of controlled decommissioning.", None, username)
    for row in finding_rows:
        update_finding(row["finding_id"], "Closed", "Closed as part of controlled decommissioning with final evidence retention.", username)
    update_euc_status(euc_id, "Decommissioned", username, "Decommissioned")
    return {"tasks_closed": len(task_rows), "findings_closed": len(finding_rows)}
