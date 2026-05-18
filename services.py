"""Business services and governance rules for the EUC Governance MVP."""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from db import UPLOAD_PATH, dataframe, execute, fetch_all, fetch_one, insert_audit, utc_now
from schema import (
    CACRT_DIMENSIONS,
    CONTROL_AREAS,
    DEFAULT_REQUIRED_ARTIFACTS,
    DOCUMENT_TYPES,
    LIFECYCLE_STATUSES,
    RISK_LEVELS,
    ROLES,
    TASK_TYPES,
)

OPEN_TASK_STATUSES = ("Open", "In Progress", "Blocked", "Closure Requested")
READ_ONLY_ROLE = "Internal Audit / Read-only User"
ADMIN_ROLE = "Group IT Governance Administrator"
GCC_ROLE = "GCC"
DVU_ROLE = "Data Validation Unit"
APPROVER_ROLE = "Approver / Head of Unit"
OWNER_ROLE = "EUC Owner"
CONTRIBUTOR_ROLE = "EUC Owner Delegate / Contributor"

ROLE_USERNAMES = {
    OWNER_ROLE: ["Maria.Papadopoulou", "Nikos.Georgiou", "Elena.Dimitriou", "Kostas.Ioannou"],
    CONTRIBUTOR_ROLE: ["EUC.Contributor", "Christina.Markou"],
    GCC_ROLE: ["GCC.User", "GCC.Monitor"],
    DVU_ROLE: ["DVU.Reviewer", "Data.Validation"],
    ADMIN_ROLE: ["Admin.User", "IT.Governance.Admin"],
    APPROVER_ROLE: ["Head.Of.Unit", "Approver.User"],
    READ_ONLY_ROLE: ["Internal.Audit", "Read.Only"],
}

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


def _default_email(username: str) -> str:
    local = re.sub(r"[^a-z0-9._-]", ".", username.lower()).strip(".") or "demo.user"
    return f"{local}@eurobank.gr"


def username_options_for_role(role: str) -> list[str]:
    """Return active usernames for the selected role.

    The MVP login remains intentionally simple, but this now reads from the
    administrator-maintained user directory when available. If the local DB is
    not initialized yet, it falls back to the seeded role defaults.
    """
    try:
        rows = fetch_all(
            "SELECT username FROM user_profiles WHERE role = ? AND active_flag = 1 ORDER BY username",
            (role,),
        )
        if rows:
            return [row["username"] for row in rows]
    except Exception:
        pass
    return ROLE_USERNAMES.get(role, ["Demo.User"])


def seed_user_profiles(username: str = "system") -> None:
    for role, users in ROLE_USERNAMES.items():
        for login in users:
            execute(
                """
                INSERT OR IGNORE INTO user_profiles(
                    username, full_name, email, role, active_flag, maker_checker_comments,
                    created_by, created_at, updated_by, updated_at
                ) VALUES (?, ?, ?, ?, 1, 'Seeded MVP user profile.', ?, ?, ?, ?)
                """,
                (
                    login,
                    login.replace(".", " "),
                    _default_email(login),
                    role,
                    username,
                    utc_now(),
                    username,
                    utc_now(),
                ),
            )


def user_profiles_table(active_only: bool = False) -> pd.DataFrame:
    sql = """
        SELECT user_id, username, full_name, email, role, active_flag, maker_checker_comments, updated_at
        FROM user_profiles
    """
    params: tuple[Any, ...] = ()
    if active_only:
        sql += " WHERE active_flag = 1"
    sql += " ORDER BY role, username"
    return dataframe(sql, params)


def get_user_profile(user_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))


def upsert_user_profile(payload: dict[str, Any], performed_by: str) -> int:
    now = utc_now()
    existing = fetch_one("SELECT * FROM user_profiles WHERE username = ?", (payload["username"],))
    if existing:
        update_user_profile(int(existing["user_id"]), payload, performed_by)
        return int(existing["user_id"])
    user_id = execute(
        """
        INSERT INTO user_profiles(
            username, full_name, email, role, active_flag, maker_checker_comments,
            created_by, created_at, updated_by, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["username"],
            payload.get("full_name"),
            payload.get("email"),
            payload["role"],
            int(bool(payload.get("active_flag", True))),
            payload.get("maker_checker_comments"),
            performed_by,
            now,
            performed_by,
            now,
        ),
    )
    insert_audit("User Profile", user_id, "CREATE", performed_by, None, payload)
    return user_id


def update_user_profile(user_id: int, payload: dict[str, Any], performed_by: str) -> None:
    old = get_user_profile(user_id)
    if not old:
        raise ValueError(f"User profile {user_id} was not found")
    execute(
        """
        UPDATE user_profiles
        SET username = ?, full_name = ?, email = ?, role = ?, active_flag = ?,
            maker_checker_comments = ?, updated_by = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (
            payload["username"],
            payload.get("full_name"),
            payload.get("email"),
            payload["role"],
            int(bool(payload.get("active_flag", True))),
            payload.get("maker_checker_comments"),
            performed_by,
            utc_now(),
            user_id,
        ),
    )
    insert_audit("User Profile", user_id, "UPDATE", performed_by, old, payload)


def deactivate_user_profile(user_id: int, performed_by: str) -> None:
    old = get_user_profile(user_id)
    if not old:
        raise ValueError(f"User profile {user_id} was not found")
    execute(
        "UPDATE user_profiles SET active_flag = 0, updated_by = ?, updated_at = ? WHERE user_id = ?",
        (performed_by, utc_now(), user_id),
    )
    insert_audit("User Profile", user_id, "DEACTIVATE", performed_by, old, {"active_flag": 0})


def is_read_only(role: str) -> bool:
    return role == READ_ONLY_ROLE


def can_view_all(role: str) -> bool:
    return role in {ADMIN_ROLE, GCC_ROLE, DVU_ROLE, APPROVER_ROLE, READ_ONLY_ROLE}


def can_configure(role: str) -> bool:
    return role == ADMIN_ROLE


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
    """Configurable MVP scoring rule for inherent/residual risk calculation."""
    if avg < 2.0:
        return "Low"
    if avg < 3.0:
        return "Medium"
    if avg < 4.0:
        return "High"
    return "Very High"


RISK_ORDER = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
RISK_FROM_ORDER = {value: key for key, value in RISK_ORDER.items()}

OWNER_INHERENT_LEVELS = ["Low", "Medium", "High"]
CONTROL_STATUS_CORE = ["In place and evidenced", "Partially in place", "Not in place"]
CONTROL_STATUS_WITH_NA = CONTROL_STATUS_CORE + ["N/A"]
CONTROL_COLUMNS = {
    "registration_risk_assessment": "control_registration_risk_assessment",
    "privileged_access": "control_privileged_access",
    "versioning_change_log": "control_versioning_change_log",
    "checks_reconciliations": "control_checks_reconciliations",
    "library_controls_cacrt": "control_library_controls_cacrt",
    "operating_procedure": "control_operating_procedure",
    "evidence_signoff": "control_evidence_signoff",
    "resilience": "control_resilience",
}
RESIDUAL_MATRIX = {
    "Very High": {"Strong": "Medium", "Adequate": "High", "Weak": "Very High", "Not in place": "Very High"},
    "High": {"Strong": "Low", "Adequate": "Medium", "Weak": "High", "Not in place": "High"},
    "Medium": {"Strong": "Low", "Adequate": "Low", "Weak": "Medium", "Not in place": "Medium"},
    "Low": {"Strong": "Low", "Adequate": "Low", "Weak": "Low", "Not in place": "Low"},
}
REQUIRED_ACTION_BY_RESIDUAL = {
    "Very High": "Outside tolerance; escalation and time-bound remediation required; do not operate material-report EUCs with unmitigated Very High residual risk.",
    "High": "Remediation plan required with target dates; consider exception governance if temporary operation is needed.",
    "Medium": "Operate with monitoring and timely remediation of gaps.",
    "Low": "Maintain controls and reassess on change.",
}


def _risk_score(level: str | None) -> int:
    return RISK_ORDER.get(str(level or "Medium"), 2)


def _max_risk(levels: list[str]) -> str:
    return RISK_FROM_ORDER[max(_risk_score(level) for level in levels)]


def derive_control_effectiveness(statuses: list[str]) -> str:
    """Replicate the workbook's derived control effectiveness logic.

    N/A is passive: it is part of the denominator but does not count as
    evidenced, partial, or not-in-place. This matches the Excel formulas.
    """
    total = len(statuses)
    not_in_place = statuses.count("Not in place")
    evidenced = statuses.count("In place and evidenced")
    partial = statuses.count("Partially in place")
    if not_in_place >= 2:
        return "Not in place"
    if not_in_place == 1:
        return "Weak"
    if partial == total:
        return "Weak"
    if evidenced > total / 2:
        return "Strong"
    if evidenced >= 1:
        return "Adequate"
    return "Adequate"


def calculate_excel_risk_assessment(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate risk exactly according to the uploaded Excel workbook.

    The owner-entered inherent levels are retained separately. BCBS 239
    materiality forces only the effective inherent risk dimensions to Very High.
    Residual risk then follows the workbook matrix, with a Medium floor for
    material BCBS 239 EUCs.
    """
    materiality_answers = [payload.get("materiality_q1"), payload.get("materiality_q2"), payload.get("materiality_q3")]
    material = any(str(answer).strip().lower() == "yes" for answer in materiality_answers)
    owner_integrity = payload.get("owner_integrity_inherent") or payload.get("integrity_inherent") or "Medium"
    owner_timeliness = payload.get("owner_timeliness_inherent") or payload.get("timeliness_inherent") or "Medium"
    if owner_integrity not in OWNER_INHERENT_LEVELS:
        owner_integrity = "Medium"
    if owner_timeliness not in OWNER_INHERENT_LEVELS:
        owner_timeliness = "Medium"

    effective_integrity = "Very High" if material else owner_integrity
    effective_timeliness = "Very High" if material else owner_timeliness

    controls = {key: payload.get(column) or "Partially in place" for key, column in CONTROL_COLUMNS.items()}
    integrity_statuses = [
        controls["registration_risk_assessment"],
        controls["privileged_access"],
        controls["versioning_change_log"],
        controls["checks_reconciliations"],
        controls["library_controls_cacrt"],
        controls["operating_procedure"],
        controls["evidence_signoff"],
    ]
    timeliness_statuses = [
        controls["registration_risk_assessment"],
        controls["privileged_access"],
        controls["library_controls_cacrt"],
        controls["evidence_signoff"],
        controls["resilience"],
    ]

    integrity_effectiveness = derive_control_effectiveness(integrity_statuses)
    timeliness_effectiveness = derive_control_effectiveness(timeliness_statuses)
    integrity_residual = RESIDUAL_MATRIX[effective_integrity][integrity_effectiveness]
    timeliness_residual = RESIDUAL_MATRIX[effective_timeliness][timeliness_effectiveness]
    overall_inherent = _max_risk([effective_integrity, effective_timeliness])
    overall_residual = _max_risk([integrity_residual, timeliness_residual])
    if material and _risk_score(overall_residual) < _risk_score("Medium"):
        overall_residual = "Medium"

    return {
        "materially_supports_bcbs239": "Yes" if material else "No",
        "owner_integrity_inherent": owner_integrity,
        "owner_timeliness_inherent": owner_timeliness,
        "effective_integrity_inherent": effective_integrity,
        "effective_timeliness_inherent": effective_timeliness,
        "integrity_control_effectiveness": integrity_effectiveness,
        "timeliness_control_effectiveness": timeliness_effectiveness,
        "integrity_residual_risk": integrity_residual,
        "timeliness_residual_risk": timeliness_residual,
        "overall_inherent_risk": overall_inherent,
        "overall_residual_risk": overall_residual,
        "required_action": REQUIRED_ACTION_BY_RESIDUAL[overall_residual],
    }


def generate_reference_id() -> str:
    row = fetch_one("SELECT COALESCE(MAX(euc_id), 0) + 1 AS next_id FROM eucs")
    return f"EUC-{int(row['next_id']):06d}"


def all_eucs(role: str | None = None, username: str | None = None) -> pd.DataFrame:
    if role and username and not can_view_all(role):
        return dataframe(
            """
            SELECT * FROM eucs
            WHERE owner = ? OR owner_delegate = ? OR created_by = ?
            ORDER BY euc_id DESC
            """,
            (username, username, username),
        )
    return dataframe("SELECT * FROM eucs ORDER BY euc_id DESC")


def dashboard_euc_scope_condition(username: str, role: str, alias: str = "e") -> tuple[str, list[Any]]:
    """Return SQL filtering for the personal Home/Dashboard scope.

    The portfolio pages intentionally retain role-wide visibility. The Home/Dashboard
    is personal: it includes EUCs directly owned/delegated/created by the user, plus
    EUCs with tasks or findings specifically assigned to the user. For centralized
    governance roles, role-queue tasks are also included because those records are
    operationally assigned to that role.
    """
    a = alias
    include_role_queue = role in {GCC_ROLE, DVU_ROLE, ADMIN_ROLE, APPROVER_ROLE}
    task_assignment = "dt.assigned_to = ? OR dt.assigned_role = ?" if include_role_queue else "dt.assigned_to = ?"
    params: list[Any] = [username, username, username, username]
    if include_role_queue:
        params.append(role)
    params.extend([username, username])
    return (
        f"""(
            {a}.owner = ?
            OR {a}.owner_delegate = ?
            OR {a}.created_by = ?
            OR EXISTS (
                SELECT 1 FROM tasks dt
                WHERE dt.euc_id = {a}.euc_id
                  AND ({task_assignment})
            )
            OR EXISTS (
                SELECT 1 FROM findings df
                WHERE df.euc_id = {a}.euc_id
                  AND (df.assigned_to = ? OR df.created_by = ?)
            )
        )""",
        params,
    )


def dashboard_eucs(role: str, username: str) -> pd.DataFrame:
    condition, params = dashboard_euc_scope_condition(username, role, "e")
    return dataframe(f"SELECT e.* FROM eucs e WHERE {condition} ORDER BY e.euc_id DESC", tuple(params))


def get_dashboard_tasks(role: str, username: str, open_only: bool = True) -> pd.DataFrame:
    include_role_queue = role in {GCC_ROLE, DVU_ROLE, ADMIN_ROLE, APPROVER_ROLE}
    if include_role_queue:
        assignment_sql = "(t.assigned_to = ? OR t.assigned_role = ? OR e.owner = ? OR e.owner_delegate = ? OR e.created_by = ?)"
        params: list[Any] = [username, role, username, username, username]
    else:
        assignment_sql = "(t.assigned_to = ? OR e.owner = ? OR e.owner_delegate = ? OR e.created_by = ?)"
        params = [username, username, username, username]
    where = [assignment_sql]
    if open_only:
        where.append("t.status IN ('Open','In Progress','Blocked','Closure Requested')")
    sql = """
        SELECT t.*, e.reference_id, e.name AS euc_name, e.owner, e.residual_risk,
               CASE WHEN t.due_date IS NOT NULL AND date(t.due_date) < date('now') AND t.status NOT IN ('Closed','Cancelled') THEN 1 ELSE 0 END AS overdue
        FROM tasks t
        LEFT JOIN eucs e ON e.euc_id = t.euc_id
        WHERE """ + " AND ".join(where) + """
        ORDER BY overdue DESC, date(t.due_date), t.priority DESC
    """
    return dataframe(sql, tuple(params))



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

    now = utc_now()
    reference_id = generate_reference_id()
    euc_id = execute(
        """
        INSERT INTO eucs(
            reference_id, name, description, purpose, owner, owner_delegate, business_unit, technology_type,
            storage_location, frequency, schedule, cut_off, business_context, bcbs239_output_mapping, cde_linkage,
            inputs, outputs, recipients, dependencies, spof_indicator, inherent_risk, residual_risk,
            overall_status, documentation_completeness_status, lifecycle_status, next_review_date,
            industrialization_rationale, decommissioning_rationale, created_by, created_at, updated_at,
            mapping_na_justification
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            reference_id,
            payload.get("name"),
            payload.get("description"),
            payload.get("purpose"),
            payload.get("owner"),
            payload.get("owner_delegate"),
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
        title=f"Complete risk assessment for {reference_id}",
        description="Risk assessment task generated after EUC registration.",
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
        "owner",
        "owner_delegate",
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
        "overall_status",
        "lifecycle_status",
        "next_review_date",
        "industrialization_rationale",
        "decommissioning_rationale",
        "mapping_na_justification",
    ]
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
    return dataframe("SELECT * FROM components WHERE euc_id = ? ORDER BY component_id", (euc_id,))


def get_component(component_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM components WHERE component_id = ?", (component_id,))


def create_component(payload: dict[str, Any], username: str) -> int:
    now = utc_now()
    component_id = execute(
        """
        INSERT INTO components(euc_id, component_name, component_type, technology, storage_location, description, criticality, owner, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload["component_name"],
            payload["component_type"],
            payload.get("technology"),
            payload.get("storage_location"),
            payload.get("description"),
            payload.get("criticality"),
            payload.get("owner"),
            now,
        ),
    )
    insert_audit("Component", component_id, "CREATE", username, None, payload)
    return component_id


def update_component(component_id: int, payload: dict[str, Any], username: str) -> None:
    old = get_component(component_id)
    if not old:
        raise ValueError("Component not found")
    allowed_fields = ["component_name", "component_type", "technology", "storage_location", "description", "criticality", "owner"]
    assignments = ", ".join([f"{field} = ?" for field in allowed_fields])
    values = [payload.get(field, old.get(field)) for field in allowed_fields]
    values.append(component_id)
    execute(f"UPDATE components SET {assignments} WHERE component_id = ?", tuple(values))
    insert_audit("Component", component_id, "UPDATE", username, old, payload)


def get_risk_assessments(euc_id: int) -> pd.DataFrame:
    return dataframe("SELECT * FROM risk_assessments WHERE euc_id = ? ORDER BY version DESC", (euc_id,))


def create_risk_assessment(payload: dict[str, Any], username: str) -> int:
    """Create a versioned risk assessment.

    Supports both the legacy MVP slider payload and the Excel-aligned payload.
    The current UI uses the Excel-aligned path. Legacy support is retained so
    old seed data or demo scripts continue to run.
    """
    is_excel_payload = any(key in payload for key in ("materiality_q1", "owner_integrity_inherent", "control_registration_risk_assessment"))

    if is_excel_payload:
        calculated = calculate_excel_risk_assessment(payload)
        inherent_risk = calculated["overall_inherent_risk"]
        residual_risk = calculated["overall_residual_risk"]
        integrity_score = _risk_score(calculated["owner_integrity_inherent"])
        timeliness_score = _risk_score(calculated["owner_timeliness_inherent"])
        complexity_score = int(payload.get("complexity_score") or 1)
        business_score = int(payload.get("business_criticality_score") or _risk_score(inherent_risk))
        effect_rank = {"Strong": 1, "Adequate": 2, "Weak": 3, "Not in place": 4}
        control_effectiveness_score = max(
            effect_rank[calculated["integrity_control_effectiveness"]],
            effect_rank[calculated["timeliness_control_effectiveness"]],
        )
    else:
        scores = [
            int(payload["integrity_accuracy_score"]),
            int(payload["timeliness_availability_score"]),
            int(payload["complexity_score"]),
            int(payload["business_criticality_score"]),
        ]
        control_effectiveness_score = int(payload["control_effectiveness_score"])
        inherent_avg = sum(scores) / len(scores)
        residual_avg = (sum(scores) + control_effectiveness_score) / 5
        inherent_risk = risk_level_from_average(inherent_avg)
        residual_risk = risk_level_from_average(residual_avg)
        integrity_score, timeliness_score, complexity_score, business_score = scores
        calculated = {
            "materially_supports_bcbs239": payload.get("materially_supports_bcbs239", "No"),
            "owner_integrity_inherent": RISK_FROM_ORDER.get(min(max(integrity_score, 1), 4), inherent_risk),
            "owner_timeliness_inherent": RISK_FROM_ORDER.get(min(max(timeliness_score, 1), 4), inherent_risk),
            "effective_integrity_inherent": inherent_risk,
            "effective_timeliness_inherent": inherent_risk,
            "integrity_control_effectiveness": "Adequate",
            "timeliness_control_effectiveness": "Adequate",
            "integrity_residual_risk": residual_risk,
            "timeliness_residual_risk": residual_risk,
            "overall_inherent_risk": inherent_risk,
            "overall_residual_risk": residual_risk,
            "required_action": REQUIRED_ACTION_BY_RESIDUAL.get(residual_risk, "Maintain controls and reassess on change."),
        }

    row = fetch_one("SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM risk_assessments WHERE euc_id = ?", (payload["euc_id"],))
    version = int(row["next_version"])
    now = utc_now()
    assessment_id = execute(
        """
        INSERT INTO risk_assessments(
            euc_id, assessment_date, assessed_by, integrity_accuracy_score, timeliness_availability_score,
            complexity_score, business_criticality_score, control_effectiveness_score, inherent_risk, residual_risk,
            materiality_q1, materiality_q2, materiality_q3, materially_supports_bcbs239,
            owner_integrity_inherent, owner_timeliness_inherent, effective_integrity_inherent, effective_timeliness_inherent,
            integrity_control_effectiveness, timeliness_control_effectiveness, integrity_residual_risk, timeliness_residual_risk,
            overall_inherent_risk, overall_residual_risk, required_action,
            control_registration_risk_assessment, control_privileged_access, control_versioning_change_log,
            control_checks_reconciliations, control_library_controls_cacrt, control_operating_procedure,
            control_evidence_signoff, control_resilience,
            rationale, trigger_type, version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["euc_id"],
            payload.get("assessment_date", date.today().isoformat()),
            payload.get("assessed_by", username),
            integrity_score,
            timeliness_score,
            complexity_score,
            business_score,
            control_effectiveness_score,
            inherent_risk,
            residual_risk,
            payload.get("materiality_q1"),
            payload.get("materiality_q2"),
            payload.get("materiality_q3"),
            calculated["materially_supports_bcbs239"],
            calculated["owner_integrity_inherent"],
            calculated["owner_timeliness_inherent"],
            calculated["effective_integrity_inherent"],
            calculated["effective_timeliness_inherent"],
            calculated["integrity_control_effectiveness"],
            calculated["timeliness_control_effectiveness"],
            calculated["integrity_residual_risk"],
            calculated["timeliness_residual_risk"],
            calculated["overall_inherent_risk"],
            calculated["overall_residual_risk"],
            calculated["required_action"],
            payload.get("control_registration_risk_assessment"),
            payload.get("control_privileged_access"),
            payload.get("control_versioning_change_log"),
            payload.get("control_checks_reconciliations"),
            payload.get("control_library_controls_cacrt"),
            payload.get("control_operating_procedure"),
            payload.get("control_evidence_signoff"),
            payload.get("control_resilience"),
            payload.get("rationale"),
            payload.get("trigger_type", "Periodic"),
            version,
            now,
        ),
    )
    lifecycle = "Awaiting Documentation" if residual_risk in {"Low", "Medium", "High", "Very High"} else "Registered"
    execute(
        """
        UPDATE eucs
        SET inherent_risk = ?, residual_risk = ?, lifecycle_status = ?, overall_status = ?, updated_at = ?
        WHERE euc_id = ?
        """,
        (inherent_risk, residual_risk, lifecycle, lifecycle, utc_now(), payload["euc_id"]),
    )
    insert_audit("Risk Assessment", assessment_id, "CREATE", username, None, {**payload, **calculated, "inherent_risk": inherent_risk, "residual_risk": residual_risk})
    evaluate_and_update_completeness(payload["euc_id"], username, create_missing_tasks=True)
    return assessment_id


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
    assessments = get_risk_assessments(euc_id)
    rows: list[dict[str, Any]] = []
    for _, req in required.iterrows():
        doc_type = req["required_document_type"]
        if doc_type == "Risk Assessment":
            if assessments.empty:
                status = "Missing"
                document_id = None
                assessment_id = None
                reviewed_by = None
                comments = "Complete the Risk Assessment module for this EUC. No upload is required."
            else:
                latest = assessments.iloc[0]
                status = "Accepted"
                document_id = None
                assessment_id = int(latest["assessment_id"])
                reviewed_by = latest.get("assessed_by")
                comments = f"Satisfied by risk assessment #{assessment_id}, version {latest.get('version')}."
        else:
            matching = docs[docs["document_type"] == doc_type] if not docs.empty else pd.DataFrame()
            assessment_id = None
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
                "assessment_id": assessment_id,
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
            title = f"Provide mandatory {row['document_type']}"
            existing = fetch_one(
                """
                SELECT task_id FROM tasks
                WHERE euc_id = ? AND task_type = 'Missing evidence' AND title = ? AND status IN ('Open','In Progress','Blocked')
                """,
                (euc_id, title),
            )
            if not existing:
                create_task(
                    euc_id=euc_id,
                    task_type="Missing evidence",
                    title=title,
                    description="Generated by required artifact checklist. Override requires an approved exception.",
                    assigned_to=euc.get("owner") if euc else None,
                    assigned_role=OWNER_ROLE,
                    due_date=add_days(DEFAULT_DUE_DAYS["Missing evidence"]),
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


def get_tasks(role: str | None = None, username: str | None = None, open_only: bool = False) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if open_only:
        where.append("t.status IN ('Open','In Progress','Blocked','Closure Requested')")
    if role and username and not can_view_all(role):
        where.append("(t.assigned_to = ? OR t.assigned_role = ?)")
        params.extend([username, role])
    elif role == APPROVER_ROLE:
        where.append("(t.assigned_role = ? OR t.assigned_to = ?)")
        params.extend([role, username])
    sql = """
        SELECT t.*, e.reference_id, e.name AS euc_name, e.owner, e.residual_risk,
               CASE WHEN t.due_date IS NOT NULL AND date(t.due_date) < date('now') AND t.status NOT IN ('Closed','Cancelled') THEN 1 ELSE 0 END AS overdue
        FROM tasks t
        LEFT JOIN eucs e ON e.euc_id = t.euc_id
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


def _count(sql: str, params: tuple[Any, ...] = ()) -> int:
    row = fetch_one(sql, params) or {"n": 0}
    return int(row.get("n") or 0)


def dashboard_metrics(role: str, username: str) -> dict[str, int]:
    condition, params = dashboard_euc_scope_condition(username, role, "e")
    values = fetch_one(
        f"""
        SELECT
            COUNT(*) AS total_eucs,
            SUM(CASE WHEN e.residual_risk IN ('High','Very High') THEN 1 ELSE 0 END) AS high_very_high,
            SUM(CASE WHEN e.lifecycle_status = 'Industrialization Candidate' THEN 1 ELSE 0 END) AS industrialization_candidates,
            SUM(CASE WHEN e.lifecycle_status = 'Decommissioned' THEN 1 ELSE 0 END) AS decommissioned,
            SUM(CASE WHEN e.documentation_completeness_status <> 'Complete' THEN 1 ELSE 0 END) AS missing_docs,
            SUM(CASE WHEN e.next_review_date IS NOT NULL AND date(e.next_review_date) < date('now') THEN 1 ELSE 0 END) AS overdue_reviews
        FROM eucs e
        WHERE {condition}
        """,
        tuple(params),
    ) or {}

    task_df = get_dashboard_tasks(role, username, open_only=True)
    open_tasks = 0 if task_df.empty else len(task_df)

    findings = _count(
        f"""
        SELECT COUNT(*) AS n
        FROM findings f
        JOIN eucs e ON e.euc_id = f.euc_id
        WHERE f.status NOT IN ('Closed','Cancelled')
          AND (f.assigned_to = ? OR f.created_by = ? OR {condition})
        """,
        tuple([username, username] + params),
    )
    exceptions = _count(
        f"""
        SELECT COUNT(*) AS n
        FROM exceptions x
        JOIN eucs e ON e.euc_id = x.euc_id
        WHERE x.status NOT IN ('Closed','Withdrawn','Rejected')
          AND {condition}
        """,
        tuple(params),
    )
    incidents = _count(
        f"""
        SELECT COUNT(*) AS n
        FROM incidents i
        JOIN eucs e ON e.euc_id = i.euc_id
        WHERE i.status <> 'Closed'
          AND {condition}
        """,
        tuple(params),
    )
    return {
        "My EUCs / relevant EUCs": int(values.get("total_eucs") or 0),
        "Missing mandatory docs": int(values.get("missing_docs") or 0),
        "Overdue reviews": int(values.get("overdue_reviews") or 0),
        "Open findings": findings,
        "Open remediation tasks": open_tasks,
        "Open exceptions": exceptions,
        "Open incidents": incidents,
        "High / Very High EUCs": int(values.get("high_very_high") or 0),
        "Industrialization candidates": int(values.get("industrialization_candidates") or 0),
        "Decommissioned EUCs": int(values.get("decommissioned") or 0),
    }


def chart_data(role: str, username: str) -> dict[str, pd.DataFrame]:
    condition, params = dashboard_euc_scope_condition(username, role, "e")
    return {
        "by_lifecycle": dataframe(
            f"""SELECT e.lifecycle_status, COUNT(*) AS count
                FROM eucs e WHERE {condition}
                GROUP BY e.lifecycle_status ORDER BY count DESC""",
            tuple(params),
        ),
        "by_risk": dataframe(
            f"""SELECT e.residual_risk, COUNT(*) AS count
                FROM eucs e WHERE {condition}
                GROUP BY e.residual_risk""",
            tuple(params),
        ),
        "by_business_unit": dataframe(
            f"""SELECT e.business_unit, COUNT(*) AS count
                FROM eucs e WHERE {condition}
                GROUP BY e.business_unit ORDER BY count DESC""",
            tuple(params),
        ),
        "tasks_by_status": dataframe(
            """SELECT t.status, COUNT(*) AS count
                FROM tasks t
                LEFT JOIN eucs e ON e.euc_id = t.euc_id
                WHERE (t.assigned_to = ? OR e.owner = ? OR e.owner_delegate = ? OR e.created_by = ?
                       OR (? IN ('GCC','Data Validation Unit','Group IT Governance Administrator','Approver / Head of Unit') AND t.assigned_role = ?))
                GROUP BY t.status""",
            (username, username, username, username, role, role),
        ),
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


def due_date_rules_table() -> pd.DataFrame:
    return dataframe("SELECT * FROM due_date_rules ORDER BY task_type, risk_level")


def initialize_reference_data(username: str = "system") -> None:
    seed_required_rules(username)
    seed_user_profiles(username)
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
