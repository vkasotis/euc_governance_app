"""Business services and governance rules for the EUC Governance MVP."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
from typing import Any

import pandas as pd

from db import UPLOAD_PATH, dataframe, execute, fetch_all, fetch_one, insert_audit, utc_now
from schema import (
    BCBS239_OUTPUTS,
    BCBS239_OUTPUT_TYPES,
    BUSINESS_UNITS,
    CDE_LINKAGE_OPTIONS,
    CACRT_DIMENSIONS,
    CONTROL_AREAS,
    CONTROLLED_STORAGE_TYPES,
    DEFAULT_REQUIRED_ARTIFACTS,
    DOCUMENT_TYPES,
    LEGAL_ENTITIES,
    LEVELS_OF_AUTOMATION,
    LIFECYCLE_STATUSES,
    RACI_PARTIES,
    RACI_RULE_DEFINITIONS,
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
IOF_ROLE = "IOF"
DATA_GOVERNANCE_ROLE = "Data Governance"
GRM_STRATEGY_ROLE = "GRM Strategy & Oversight / Projects (Group Finance)"
DEFAULT_EMAIL_ADDRESS = "ekassotis@eurobank.gr"

RACI_PARTY_TO_PROFILE_ROLE = {
    "EUC Owner": OWNER_ROLE,
    "Data Validation Unit": DVU_ROLE,
    "GCC": GCC_ROLE,
    "Group IT Governance": ADMIN_ROLE,
    "IOF": IOF_ROLE,
    "Data Governance": DATA_GOVERNANCE_ROLE,
    "Internal Audit": READ_ONLY_ROLE,
    "GRM Strategy & Oversight / Projects (Group Finance)": GRM_STRATEGY_ROLE,
}

ROLE_USERNAMES = {
    OWNER_ROLE: ["Maria.Papadopoulou", "Nikos.Georgiou", "Elena.Dimitriou", "Kostas.Ioannou"],
    CONTRIBUTOR_ROLE: ["EUC.Contributor", "Christina.Markou"],
    GCC_ROLE: ["GCC.User", "GCC.Monitor"],
    DVU_ROLE: ["DVU.Reviewer", "Data.Validation"],
    ADMIN_ROLE: ["Admin.User", "IT.Governance.Admin"],
    APPROVER_ROLE: ["Head.Of.Unit", "Approver.User"],
    READ_ONLY_ROLE: ["Internal.Audit", "Read.Only"],
}

RACI_ONLY_ROLE_USERNAMES = {
    IOF_ROLE: ["IOF.User"],
    DATA_GOVERNANCE_ROLE: ["Data.Governance"],
    GRM_STRATEGY_ROLE: ["GRM.Projects"],
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


ARTIFACT_UPLOAD_GUIDANCE = {
    "Risk Assessment": "No separate file upload is expected. Complete the Risk Assessment module; it remains Submitted until GCC/Data Validation review accepts it.",
    "Operating Procedure": "Runbook or operating procedure covering purpose, inputs, execution steps, cut-offs, checkpoints, fallback, distribution and evidence references.",
    "Library of Controls": "EUC control library mapped to CACRT categories, with control owner, frequency, thresholds, exception handling, escalation, evidence location and retention.",
    "Change & Versioning Evidence": "Current version/change information, release log, version history, release notes, material-change request/rationale, impact assessment, approvals, cut-over or rollback evidence where applicable.",
    "Design / Logic Evidence": "Required only where material business logic, automated processing, complex calculations, scripts, macros, transformations, critical assumptions or mappings are not readily understood through the Operating Procedure alone.",
    "Control Evidence": "Evidence that key input/output completeness, accuracy, timeliness, exception and control checks operated for the relevant run or review period.",
    "Testing Evidence": "Unit, functional, regression or challenger testing outputs, test cases, results, defects and sign-off. Mandatory for new go-live and triggered situations; not retrospectively recreated for legacy onboarding.",
    "UAT Evidence": "UAT plan, scenarios, data used, steps, results, issues, conclusions and formal user/head-of-unit sign-off. Mandatory for new go-live and triggered situations; not retrospectively recreated for legacy onboarding.",
    "Approval Evidence": "Approval email, workflow/ticket sign-off, Head of Unit approval, Senior Management approval or committee escalation evidence, depending on risk and trigger.",
    "Access Review Evidence": "Evidence of named roles, ACL/RLS where applicable, privileged access control, leaver/role-change revocation or event-driven access review. No fixed annual/semi-annual/quarterly frequency is imposed by Appendix 4.",
    "Review Evidence": "Dated independent/four-eye, governance, management-attestation or review evidence identifying the EUC, review/run scope, checks performed, issues identified, reviewer conclusion and remediation actions where applicable.",
    "Reconciliation Evidence": "Reconciliations to authoritative sources or benchmarks, control totals, variance thresholds, explained deltas and reviewer sign-off.",
    "Resilience Evidence": "Backup verification, restore drill or equivalent where required, BCP/fallback steps, deputy-cover evidence, dependency monitoring and SPOF mitigation.",
    "Exception Record": "Approved exception record with control gap, root cause, compensating controls, residual risk, target date, expiry date and monitoring plan.",
    "Incident & RCA Evidence": "Incident record, containment, correction/re-issue evidence, impact assessment, root-cause analysis, corrective/preventive actions, owners and dates.",
    "Archive Evidence": "Final released version, final evidence pack, approved archive location and retention confirmation.",
    "Access Revocation Evidence": "Proof that access to legacy/decommissioned locations was revoked and distribution routes disabled.",
    "Industrialization Assessment Evidence": "Industrialization rationale, prioritization score, project/BEF submission, decision record and delivery-pipeline reference.",
    "Decommissioning Evidence": "Decommissioning approval, final archive, access revocation, open-obligation closure and inventory status update evidence.",
}

LEGACY_DOCUMENT_TYPE_ALIASES = {
    "Versioning / Change Log Evidence": "Change & Versioning Evidence",
    "Change Evidence": "Change & Versioning Evidence",
    "Incident Evidence": "Incident & RCA Evidence",
    "Incident RCA Evidence": "Incident & RCA Evidence",
    "Containment / Correction Evidence": "Incident & RCA Evidence",
    "Independent / Periodic Review Evidence": "Review Evidence",
    "Exception Closure Evidence": "Exception Record",
    "Evidence Pack Index": None,
}

REQUIREMENT_CLASSIFICATIONS = {
    "MANDATORY": "Mandatory baseline",
    "CONDITIONAL": "Conditional mandatory",
    "WHERE_APPLICABLE": "Where applicable",
    "EVENT": "Event-driven",
    "GUIDANCE": "Guidance only",
}

def canonical_document_type(document_type: str | None) -> str | None:
    doc_type = str(document_type or "").strip()
    if not doc_type:
        return None
    return LEGACY_DOCUMENT_TYPE_ALIASES.get(doc_type, doc_type)


def artifact_upload_guidance(document_type: str) -> str:
    canonical = canonical_document_type(document_type) or str(document_type or "")
    return ARTIFACT_UPLOAD_GUIDANCE.get(
        canonical,
        "Upload evidence sufficient for the reviewer to verify the specific requirement, control operation, owner, date, scope and conclusion.",
    )


def artifact_user_action(document_type: str, status: str | None = None) -> str:
    """Return action-oriented guidance for a checklist artifact.

    The app must not make Review Evidence look like a universal requirement.
    Each artifact type receives targeted instructions, while the status controls
    whether the owner should act now, wait for review, or no longer needs to act.
    """
    doc_type = canonical_document_type(document_type) or str(document_type or "").strip()
    normalized_status = str(status or "Missing").strip() or "Missing"
    if doc_type == "Risk Assessment":
        base = "Complete or update the Risk Assessment module for this EUC. Do not upload a separate risk-assessment file. The assessment remains Submitted until GCC/Data Validation accepts or rejects it."
    else:
        base = artifact_upload_guidance(doc_type)

    if normalized_status == "Accepted":
        return f"No current owner action for this artifact. Accepted evidence is already on file. Evidence expectation: {base}"
    if normalized_status == "Submitted":
        return f"Evidence has been submitted and is awaiting reviewer action. Monitor review comments; replace or supplement evidence only if GCC/Data Validation rejects it. Evidence expectation: {base}"
    if normalized_status == "Rejected":
        return f"Replace or correct the rejected evidence and resubmit it under this document type. Address the reviewer comments/deficiency tag before resubmission. Evidence expectation: {base}"
    if normalized_status == "Expired":
        return f"Upload a refreshed/current version of this evidence and submit it for review. Evidence expectation: {base}"
    if normalized_status == "Superseded":
        return f"Confirm the superseding evidence is uploaded and accepted. Upload a current replacement if no accepted replacement exists. Evidence expectation: {base}"
    if normalized_status == "Pending":
        return f"Submit the required evidence for reviewer assessment. Evidence expectation: {base}"
    return f"Provide this missing artifact where it is mandatory or currently triggered for this EUC. Evidence expectation: {base}"


def _extract_artifact_from_task(title: str | None, description: str | None = None) -> str | None:
    """Infer a document type from task wording when one is present."""
    text = f"{title or ''} {description or ''}".strip()
    for prefix, suffix in [
        ("Provide mandatory ", ""),
        ("Replace rejected ", " evidence"),
        ("Upload ", " evidence"),
    ]:
        if prefix in text:
            candidate = text.split(prefix, 1)[1]
            if suffix and suffix in candidate:
                candidate = candidate.split(suffix, 1)[0]
            candidate = candidate.split(".", 1)[0].split(";", 1)[0].strip()
            if candidate in ARTIFACT_UPLOAD_GUIDANCE or candidate == "Risk Assessment":
                return candidate
    for doc_type in sorted(ARTIFACT_UPLOAD_GUIDANCE, key=len, reverse=True):
        if doc_type.lower() in text.lower():
            return doc_type
    return None


def task_user_action_guidance(task: dict[str, Any] | pd.Series) -> str:
    """Return task-specific instructions for Tasks & Remediation.

    Guidance is based on the task type and, where possible, the document/artifact
    referenced by the title or description. This prevents review-signoff wording
    from being reused for unrelated requests.
    """
    if isinstance(task, pd.Series):
        row = task.to_dict()
    else:
        row = dict(task or {})
    task_type = str(row.get("task_type") or "").strip()
    title = str(row.get("title") or "").strip()
    description = str(row.get("description") or "").strip()
    artifact = _extract_artifact_from_task(title, description)

    if task_type in {"Risk assessment", "Reassessment"}:
        return "Go to the Risk Assessment page for this EUC, complete or amend the assessment, and submit it. No separate risk-assessment file should be uploaded."
    if task_type in {"Document submission", "Missing evidence", "Documentation refresh"}:
        if artifact:
            return f"Go to Documents & Evidence Pack and upload/refresh `{artifact}` for this EUC. {artifact_user_action(artifact, 'Missing')}"
        return "Go to Documents & Evidence Pack, review the Required Artifact Checklist, and upload or refresh the specific missing/rejected/expired artifact shown for this EUC."
    if task_type == "Remediation":
        return "Review the related finding, residual-risk issue, or reviewer comment; remediate the control/data/documentation gap; upload closure evidence where needed; then update the task with the closure response and evidence document ID."
    if task_type == "Review response":
        if "exception" in title.lower() or "exception" in description.lower():
            return "Review the exception request and supporting evidence. Approvers should approve/reject in the Exceptions page; owners should address comments or provide additional evidence if returned."
        return "Review the GCC/Data Validation outcome or challenge comments, respond to each point, upload any requested supporting evidence, and update the task with your response."
    if task_type == "Closure evidence":
        return "Upload evidence proving the remediation/action is complete, record the evidence document ID on this task, and provide a closure reason/request."
    if task_type == "Registration completion":
        return "Complete the EUC registration fields, including owner/reviewer, business unit, BCBS 239 mapping/scope indicators, schedule/cut-off, storage and dependency details."
    return "Review the task title and description, complete the requested action, upload supporting evidence only if the task requires evidence, and update the task status/closure response."


def _default_email(username: str) -> str:
    """Return the default seeded demo mailbox.

    This value is only used to initialize demo users. Administrators can later
    change each user's email address in Admin Configuration.
    """
    return DEFAULT_EMAIL_ADDRESS


def _clean_email(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


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
    directory_seed_users = {**ROLE_USERNAMES, **RACI_ONLY_ROLE_USERNAMES}
    for role, users in directory_seed_users.items():
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


def sync_all_email_addresses(performed_by: str = "system") -> None:
    """One-off admin utility: update every stored user and queued notification email.

    This function is intentionally *not* called during normal startup. It is kept
    for controlled demo resets only. User emails remain editable from the UI.
    """
    rows = fetch_all("SELECT user_id, username, email FROM user_profiles")
    now = utc_now()
    for row in rows:
        if (row.get("email") or "") == DEFAULT_EMAIL_ADDRESS:
            continue
        execute(
            "UPDATE user_profiles SET email = ?, updated_by = ?, updated_at = ? WHERE user_id = ?",
            (DEFAULT_EMAIL_ADDRESS, performed_by, now, row["user_id"]),
        )
        insert_audit(
            "User Profile",
            row["user_id"],
            "EMAIL_SYNC",
            performed_by,
            {"username": row.get("username"), "email": row.get("email")},
            {"username": row.get("username"), "email": DEFAULT_EMAIL_ADDRESS},
        )
    execute(
        "UPDATE notification_outbox SET recipient_email = ? WHERE recipient_email IS NOT NULL AND recipient_email <> '' AND recipient_email <> ?",
        (DEFAULT_EMAIL_ADDRESS, DEFAULT_EMAIL_ADDRESS),
    )


def seed_bcbs239_outputs(username: str = "system") -> None:
    """Load the controlled BCBS 239 material report/output list.

    Values were sourced from the uploaded workbook:
    `BCBS 239 inventory of material reports.xlsx`, sheet `Detailed Inventory`,
    column D (`Report`). The list is persisted in a configurable table so Group
    IT Governance can maintain it from Admin Configuration.
    """
    now = utc_now()
    for output_name in BCBS239_OUTPUTS:
        execute(
            """
            INSERT OR IGNORE INTO bcbs239_outputs(
                output_name, output_type, active_flag, maker_checker_comments,
                created_by, created_at, updated_by, updated_at
            ) VALUES (?, 'Material Report', 1, 'Seeded from BCBS 239 material reports inventory.', ?, ?, ?, ?)
            """,
            (output_name, username, now, username, now),
        )


def bcbs239_outputs_table(active_only: bool = False) -> pd.DataFrame:
    sql = """
        SELECT output_id, output_name, output_type, owner, active_flag, maker_checker_comments, updated_at
        FROM bcbs239_outputs
    """
    params: tuple[Any, ...] = ()
    if active_only:
        sql += " WHERE active_flag = 1"
    sql += " ORDER BY output_name"
    return dataframe(sql, params)


def bcbs239_output_options(active_only: bool = True, output_type: str | None = None) -> list[str]:
    where = []
    params: list[Any] = []
    if active_only:
        where.append("active_flag = 1")
    if output_type:
        where.append("output_type = ?")
        params.append(output_type)
    sql = "SELECT output_name FROM bcbs239_outputs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY output_name"
    rows = fetch_all(sql, tuple(params))
    values = [row["output_name"] for row in rows if row.get("output_name")]
    if values:
        return values
    return sorted(BCBS239_OUTPUTS) if output_type in (None, "Material Report") else []


def active_user_options(role: str | None = None, include_blank: bool = False) -> list[str]:
    sql = "SELECT username FROM user_profiles WHERE active_flag = 1"
    params: list[Any] = []
    if role:
        sql += " AND role = ?"
        params.append(role)
    sql += " ORDER BY username"
    rows = fetch_all(sql, tuple(params))
    values = [row["username"] for row in rows if row.get("username")]
    if not values:
        if role:
            values = ROLE_USERNAMES.get(role, [])
        else:
            values = sorted({u for users in ROLE_USERNAMES.values() for u in users})
    return ([""] if include_blank else []) + values


def reference_options(category: str, fallback: list[str] | None = None, include_blank: bool = False) -> list[str]:
    rows = fetch_all(
        "SELECT value FROM reference_data WHERE category = ? AND active_flag = 1 ORDER BY value",
        (category,),
    )
    values = [row["value"] for row in rows if row.get("value")]
    if not values:
        values = list(fallback or [])
    return ([""] if include_blank else []) + values


def upsert_bcbs239_output(payload: dict[str, Any], performed_by: str) -> int:
    output_name = str(payload.get("output_name") or "").strip()
    if not output_name:
        raise ValueError("BCBS 239 output name is required.")
    existing = fetch_one("SELECT * FROM bcbs239_outputs WHERE output_name = ?", (output_name,))
    now = utc_now()
    if existing:
        execute(
            """
            UPDATE bcbs239_outputs
            SET output_type = ?, owner = ?, active_flag = ?, maker_checker_comments = ?,
                updated_by = ?, updated_at = ?
            WHERE output_id = ?
            """,
            (
                payload.get("output_type") or existing.get("output_type") or "Material Report",
                payload.get("owner"),
                int(bool(payload.get("active_flag", True))),
                payload.get("maker_checker_comments"),
                performed_by,
                now,
                existing["output_id"],
            ),
        )
        insert_audit("BCBS239 Output", existing["output_id"], "UPDATE", performed_by, existing, payload)
        return int(existing["output_id"])
    output_id = execute(
        """
        INSERT INTO bcbs239_outputs(
            output_name, output_type, owner, active_flag, maker_checker_comments,
            created_by, created_at, updated_by, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            output_name,
            payload.get("output_type") or "Material Report",
            payload.get("owner"),
            int(bool(payload.get("active_flag", True))),
            payload.get("maker_checker_comments"),
            performed_by,
            now,
            performed_by,
            now,
        ),
    )
    insert_audit("BCBS239 Output", output_id, "CREATE", performed_by, None, payload)
    return output_id


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
            _clean_email(payload.get("email")) or DEFAULT_EMAIL_ADDRESS,
            payload["role"],
            int(bool(payload.get("active_flag", True))),
            payload.get("maker_checker_comments"),
            performed_by,
            now,
            performed_by,
            now,
        ),
    )
    insert_audit("User Profile", user_id, "CREATE", performed_by, None, {**payload, "email": _clean_email(payload.get("email")) or DEFAULT_EMAIL_ADDRESS})
    queue_raci_notifications(
        "USER_PROFILE_UPDATED",
        "User Profile",
        user_id,
        None,
        performed_by,
        context={"Username": payload.get("username"), "Role": payload.get("role"), "Action": "Created"},
    )
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
            _clean_email(payload.get("email")) or DEFAULT_EMAIL_ADDRESS,
            payload["role"],
            int(bool(payload.get("active_flag", True))),
            payload.get("maker_checker_comments"),
            performed_by,
            utc_now(),
            user_id,
        ),
    )
    insert_audit("User Profile", user_id, "UPDATE", performed_by, old, {**payload, "email": _clean_email(payload.get("email")) or DEFAULT_EMAIL_ADDRESS})
    queue_raci_notifications(
        "USER_PROFILE_UPDATED",
        "User Profile",
        user_id,
        None,
        performed_by,
        context={"Username": payload.get("username"), "Role": payload.get("role"), "Action": "Updated"},
    )


def deactivate_user_profile(user_id: int, performed_by: str) -> None:
    old = get_user_profile(user_id)
    if not old:
        raise ValueError(f"User profile {user_id} was not found")
    execute(
        "UPDATE user_profiles SET active_flag = 0, updated_by = ?, updated_at = ? WHERE user_id = ?",
        (performed_by, utc_now(), user_id),
    )
    insert_audit("User Profile", user_id, "DEACTIVATE", performed_by, old, {"active_flag": 0})
    queue_raci_notifications(
        "USER_PROFILE_UPDATED",
        "User Profile",
        user_id,
        None,
        performed_by,
        context={"Username": old.get("username"), "Role": old.get("role"), "Action": "Deactivated"},
    )


def seed_raci_rules(username: str = "system") -> None:
    """Seed the RACI matrix from Appendix 6 as event-driven notification rules."""
    now = utc_now()
    for definition in RACI_RULE_DEFINITIONS:
        activity = definition["activity_decision"]
        raci = definition["raci"]
        for event_type in definition["event_types"]:
            execute(
                """
                INSERT OR IGNORE INTO raci_rules(
                    activity_decision, event_type, euc_owner_raci, data_validation_unit_raci,
                    gcc_raci, group_it_governance_raci, iof_raci, data_governance_raci,
                    internal_audit_raci, grm_strategy_raci, active_flag, maker_checker_comments,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    activity,
                    event_type,
                    raci.get("EUC Owner", "-"),
                    raci.get("Data Validation Unit", "-"),
                    raci.get("GCC", "-"),
                    raci.get("Group IT Governance", "-"),
                    raci.get("IOF", "-"),
                    raci.get("Data Governance", "-"),
                    raci.get("Internal Audit", "-"),
                    raci.get("GRM Strategy & Oversight / Projects (Group Finance)", "-"),
                    "Seeded from Appendix 6 RACI matrix.",
                    now,
                    now,
                ),
            )


def raci_rules_table(active_only: bool = False) -> pd.DataFrame:
    sql = "SELECT * FROM raci_rules"
    if active_only:
        sql += " WHERE active_flag = 1"
    sql += " ORDER BY activity_decision, event_type"
    return dataframe(sql)


def get_raci_rule(event_type: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM raci_rules WHERE event_type = ? AND active_flag = 1", (event_type,))


def update_raci_rule(rule_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM raci_rules WHERE rule_id = ?", (rule_id,))
    if not old:
        raise ValueError("RACI rule not found")
    execute(
        """
        UPDATE raci_rules
        SET activity_decision = ?, euc_owner_raci = ?, data_validation_unit_raci = ?, gcc_raci = ?,
            group_it_governance_raci = ?, iof_raci = ?, data_governance_raci = ?, internal_audit_raci = ?,
            grm_strategy_raci = ?, active_flag = ?, maker_checker_comments = ?, updated_at = ?
        WHERE rule_id = ?
        """,
        (
            payload.get("activity_decision", old.get("activity_decision")),
            payload.get("euc_owner_raci", old.get("euc_owner_raci")),
            payload.get("data_validation_unit_raci", old.get("data_validation_unit_raci")),
            payload.get("gcc_raci", old.get("gcc_raci")),
            payload.get("group_it_governance_raci", old.get("group_it_governance_raci")),
            payload.get("iof_raci", old.get("iof_raci")),
            payload.get("data_governance_raci", old.get("data_governance_raci")),
            payload.get("internal_audit_raci", old.get("internal_audit_raci")),
            payload.get("grm_strategy_raci", old.get("grm_strategy_raci")),
            int(bool(payload.get("active_flag", old.get("active_flag", 1)))),
            payload.get("maker_checker_comments", old.get("maker_checker_comments")),
            utc_now(),
            rule_id,
        ),
    )
    insert_audit("RACI Rule", rule_id, "UPDATE", username, old, payload)


def _active_users_for_role(role: str) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT username, full_name, email, role
        FROM user_profiles
        WHERE role = ? AND active_flag = 1
        ORDER BY username
        """,
        (role,),
    )


def _user_by_username(username: str | None) -> dict[str, Any] | None:
    if not username:
        return None
    return fetch_one(
        "SELECT username, full_name, email, role FROM user_profiles WHERE username = ? AND active_flag = 1",
        (username,),
    )


def _raci_columns(rule: dict[str, Any]) -> dict[str, str | None]:
    return {
        "EUC Owner": rule.get("euc_owner_raci"),
        "Data Validation Unit": rule.get("data_validation_unit_raci"),
        "GCC": rule.get("gcc_raci"),
        "Group IT Governance": rule.get("group_it_governance_raci"),
        "IOF": rule.get("iof_raci"),
        "Data Governance": rule.get("data_governance_raci"),
        "Internal Audit": rule.get("internal_audit_raci"),
        "GRM Strategy & Oversight / Projects (Group Finance)": rule.get("grm_strategy_raci"),
    }


def _raci_recipients(rule: dict[str, Any], euc: dict[str, Any] | None) -> list[dict[str, Any]]:
    recipients: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for party, responsibility in _raci_columns(rule).items():
        responsibility = str(responsibility or "-").strip()
        if not responsibility or responsibility == "-":
            continue
        profiles: list[dict[str, Any]] = []
        if party == "EUC Owner":
            if euc:
                owner_profile = _user_by_username(euc.get("owner"))
                if owner_profile:
                    profiles.append(owner_profile)
                delegate_profile = _user_by_username(euc.get("owner_delegate"))
                if delegate_profile:
                    profiles.append(delegate_profile)
        else:
            mapped_role = RACI_PARTY_TO_PROFILE_ROLE.get(party)
            if mapped_role:
                profiles.extend(_active_users_for_role(mapped_role))
        for profile in profiles:
            key = (profile.get("username") or "", profile.get("email") or "")
            if key in seen:
                continue
            seen.add(key)
            recipients.append(
                {
                    "username": profile.get("username"),
                    "email": profile.get("email"),
                    "role": profile.get("role"),
                    "raci_party": party,
                    "raci_responsibility": responsibility,
                }
            )
    return recipients


def _insert_notification(
    *,
    event_type: str,
    activity_decision: str | None,
    entity_type: str,
    entity_id: str | int,
    euc_id: int | None,
    reference_id: str | None,
    subject: str,
    body: str,
    recipient_username: str | None,
    recipient_email: str | None,
    recipient_role: str | None,
    raci_party: str | None,
    raci_responsibility: str | None,
    created_by: str,
) -> int:
    recipient_email = _clean_email(recipient_email)
    status = "Pending" if recipient_email else "No Email"
    notification_id = execute(
        """
        INSERT INTO notification_outbox(
            event_type, activity_decision, entity_type, entity_id, euc_id, reference_id, subject, body,
            recipient_username, recipient_email, recipient_role, raci_party, raci_responsibility,
            status, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            activity_decision,
            entity_type,
            str(entity_id),
            euc_id,
            reference_id,
            subject,
            body,
            recipient_username,
            recipient_email,
            recipient_role,
            raci_party,
            raci_responsibility,
            status,
            created_by,
            utc_now(),
        ),
    )
    insert_audit("Notification", notification_id, "QUEUE", created_by, None, {"event_type": event_type, "recipient": recipient_email, "status": status})
    return notification_id


def queue_raci_notifications(
    event_type: str,
    entity_type: str,
    entity_id: str | int,
    euc_id: int | None,
    triggered_by: str,
    subject: str | None = None,
    body: str | None = None,
    context: dict[str, Any] | None = None,
) -> int:
    """Queue RACI-based email actions in the local outbox.

    The MVP does not require SMTP to be configured. Notifications are persisted
    first and can then be sent through the optional SMTP sender.
    """
    rule = get_raci_rule(event_type)
    if not rule:
        return 0
    euc = get_euc(euc_id) if euc_id else None
    reference = euc.get("reference_id") if euc else None
    euc_name = euc.get("name") if euc else "Portfolio / configuration"
    subject = subject or f"[EUC Governance] {rule.get('activity_decision')} - {reference or entity_type}"
    context = context or {}
    default_body = [
        "An EUC Governance action requires notification based on the configured RACI matrix.",
        "",
        f"Activity / decision: {rule.get('activity_decision')}",
        f"Event type: {event_type}",
        f"EUC: {reference or '-'} - {euc_name}",
        f"Entity: {entity_type} #{entity_id}",
        f"Triggered by: {triggered_by}",
    ]
    for key, value in context.items():
        if value is not None and str(value).strip() != "":
            default_body.append(f"{key}: {value}")
    default_body.extend(["", "Please review the EUC Governance Monitoring App for details."])
    body = body or "\n".join(default_body)

    count = 0
    for recipient in _raci_recipients(rule, euc):
        recipient_body = body + f"\n\nRACI role: {recipient['raci_party']} = {recipient['raci_responsibility']}"
        _insert_notification(
            event_type=event_type,
            activity_decision=rule.get("activity_decision"),
            entity_type=entity_type,
            entity_id=entity_id,
            euc_id=euc_id,
            reference_id=reference,
            subject=subject,
            body=recipient_body,
            recipient_username=recipient.get("username"),
            recipient_email=recipient.get("email"),
            recipient_role=recipient.get("role"),
            raci_party=recipient.get("raci_party"),
            raci_responsibility=recipient.get("raci_responsibility"),
            created_by=triggered_by,
        )
        count += 1
    return count


def queue_direct_notification(
    *,
    event_type: str,
    entity_type: str,
    entity_id: str | int,
    euc_id: int | None,
    triggered_by: str,
    subject: str,
    body: str,
    recipient_username: str | None = None,
    recipient_role: str | None = None,
    raci_party: str | None = None,
    raci_responsibility: str | None = None,
) -> int:
    recipients: list[dict[str, Any]] = []
    if recipient_username:
        profile = _user_by_username(recipient_username)
        if profile:
            recipients.append(profile)
    if recipient_role:
        recipients.extend(_active_users_for_role(recipient_role))
    seen: set[tuple[str, str]] = set()
    euc = get_euc(euc_id) if euc_id else None
    count = 0
    for profile in recipients:
        key = (profile.get("username") or "", profile.get("email") or "")
        if key in seen:
            continue
        seen.add(key)
        _insert_notification(
            event_type=event_type,
            activity_decision="Direct task / workflow notification",
            entity_type=entity_type,
            entity_id=entity_id,
            euc_id=euc_id,
            reference_id=euc.get("reference_id") if euc else None,
            subject=subject,
            body=body,
            recipient_username=profile.get("username"),
            recipient_email=profile.get("email"),
            recipient_role=profile.get("role"),
            raci_party=raci_party or "Workflow assignee",
            raci_responsibility=raci_responsibility or "Action owner",
            created_by=triggered_by,
        )
        count += 1
    return count


def queue_task_notification(task_id: int, triggered_by: str) -> None:
    task = fetch_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    if not task:
        return
    euc = get_euc(task.get("euc_id")) if task.get("euc_id") else None
    subject = f"[EUC Governance] Task assigned: {task.get('title')}"
    body = "\n".join(
        [
            "A task has been assigned in the EUC Governance Monitoring App.",
            "",
            f"Task: {task.get('title')}",
            f"Task type: {task.get('task_type')}",
            f"Priority: {task.get('priority')}",
            f"Due date: {task.get('due_date') or '-'}",
            f"EUC: {(euc or {}).get('reference_id', '-') } - {(euc or {}).get('name', '-')}",
            f"Created by: {triggered_by}",
            "",
            task.get("description") or "Please review and action this task.",
        ]
    )
    queue_direct_notification(
        event_type="TASK_ASSIGNED",
        entity_type="Task",
        entity_id=task_id,
        euc_id=task.get("euc_id"),
        triggered_by=triggered_by,
        subject=subject,
        body=body,
        recipient_username=task.get("assigned_to"),
        recipient_role=task.get("assigned_role") if not task.get("assigned_to") else None,
    )


def notification_outbox_table(filters: dict[str, Any] | None = None) -> pd.DataFrame:
    filters = filters or {}
    where = []
    params: list[Any] = []
    if filters.get("status") and filters["status"] != "All":
        where.append("status = ?")
        params.append(filters["status"])
    if filters.get("event_type") and filters["event_type"] != "All":
        where.append("event_type = ?")
        params.append(filters["event_type"])
    if filters.get("recipient"):
        where.append("(recipient_username LIKE ? OR recipient_email LIKE ? OR recipient_role LIKE ?)")
        pattern = f"%{filters['recipient']}%"
        params.extend([pattern, pattern, pattern])
    if filters.get("euc_id"):
        where.append("euc_id = ?")
        params.append(filters["euc_id"])
    sql = "SELECT * FROM notification_outbox"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, notification_id DESC"
    return dataframe(sql, tuple(params))


def notification_event_types() -> list[str]:
    rows = fetch_all("SELECT DISTINCT event_type FROM raci_rules UNION SELECT DISTINCT event_type FROM notification_outbox ORDER BY event_type")
    return [row["event_type"] for row in rows]


def notification_statuses() -> list[str]:
    rows = fetch_all("SELECT DISTINCT status FROM notification_outbox ORDER BY status")
    return [row["status"] for row in rows] or ["Pending", "Sent", "Failed", "No Email", "Cancelled"]


def update_notification_status(notification_id: int, status: str, username: str, error_message: str | None = None) -> None:
    old = fetch_one("SELECT * FROM notification_outbox WHERE notification_id = ?", (notification_id,))
    if not old:
        raise ValueError("Notification not found")
    execute(
        """
        UPDATE notification_outbox
        SET status = ?, sent_at = CASE WHEN ? = 'Sent' THEN ? ELSE sent_at END, error_message = ?
        WHERE notification_id = ?
        """,
        (status, status, utc_now(), error_message, notification_id),
    )
    insert_audit("Notification", notification_id, "STATUS_UPDATE", username, old, {"status": status, "error_message": error_message})


def send_pending_notifications(limit: int, username: str) -> dict[str, int]:
    """Send pending outbox entries through SMTP when configured.

    Required environment variable: SMTP_HOST. Optional variables:
    SMTP_PORT, SMTP_FROM, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS.
    SMTP_FROM defaults to DEFAULT_EMAIL_ADDRESS.
    """
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM", DEFAULT_EMAIL_ADDRESS)
    if not host:
        raise ValueError("SMTP_HOST environment variable is required to send emails. Pending notifications remain in the outbox.")
    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    rows = fetch_all(
        """
        SELECT * FROM notification_outbox
        WHERE status = 'Pending' AND recipient_email IS NOT NULL AND recipient_email <> ''
        ORDER BY created_at ASC, notification_id ASC
        LIMIT ?
        """,
        (limit,),
    )
    sent = failed = 0
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls(context=context)
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        for row in rows:
            msg = EmailMessage()
            msg["From"] = sender
            msg["To"] = row["recipient_email"]
            msg["Subject"] = row["subject"]
            msg.set_content(row["body"])
            try:
                server.send_message(msg)
                update_notification_status(row["notification_id"], "Sent", username)
                sent += 1
            except Exception as exc:  # pragma: no cover - depends on external SMTP
                update_notification_status(row["notification_id"], "Failed", username, str(exc))
                failed += 1
    return {"attempted": len(rows), "sent": sent, "failed": failed}

def is_read_only(role: str) -> bool:
    return role == READ_ONLY_ROLE


def can_view_all(role: str) -> bool:
    return role in {ADMIN_ROLE, GCC_ROLE, DVU_ROLE, APPROVER_ROLE, READ_ONLY_ROLE}


def can_configure(role: str) -> bool:
    return role == ADMIN_ROLE


def can_review(role: str) -> bool:
    # Independent review/challenge is performed by GCC or Data Validation.
    # Group IT Governance Administrator administers the platform/configuration
    # and must not approve or challenge EUC content/risk assessments.
    return role in {GCC_ROLE, DVU_ROLE}


def can_approve(role: str) -> bool:
    return role == APPROVER_ROLE


def can_edit_euc(role: str, username: str, euc: dict[str, Any] | None) -> bool:
    if not euc or is_read_only(role):
        return False
    # EUC registry content is owned by the EUC Owner/Delegate. Group IT
    # Governance Administrator remains a platform/configuration administrator,
    # not a content owner.
    if role == OWNER_ROLE and euc.get("owner") == username:
        return True
    if role == CONTRIBUTOR_ROLE and euc.get("owner_delegate") == username:
        return True
    return False


def can_upload_evidence(role: str, username: str, euc: dict[str, Any] | None) -> bool:
    # Evidence is business/control content. Owners/delegates upload; GCC/DVU
    # can add review evidence where needed. Group IT Admin does not own content.
    return can_edit_euc(role, username, euc) or role in {GCC_ROLE, DVU_ROLE}


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
BASELINE_CONTROL_GUIDANCE = {
    "registration_risk_assessment": "Confirm the EUC is registered with mandatory fields and primary BCBS 239 output mapping complete, and that the EUC Risk Assessment has been independently reviewed/accepted. A submitted but unreviewed assessment is not enough for 'In place and evidenced'.",
    "privileged_access": "Access must be restricted to named roles/users, least privilege must apply, key formulas/logic/structure should be protected, and leavers/role changes should be revoked promptly.",
    "versioning_change_log": "Use controlled storage/repositories, release tags, version history and change logs covering formulas, code, thresholds, sources, outputs, recipients and paths.",
    "checks_reconciliations": "Validate input and output completeness, accuracy and timeliness using row counts, totals, range/format checks, reconciliations, threshold checks and exception handling.",
    "library_controls_cacrt": "Maintain a Library of Controls mapped to CACRT dimensions: Consistency, Accuracy, Completeness, Reconciliation and Timeliness, including owner, frequency, threshold, escalation and evidence location.",
    "operating_procedure": "Maintain a runbook/operating procedure covering purpose, inputs, steps, cut-offs, controls, reconciliations, sign-offs, distribution, fallback steps and evidence references.",
    "evidence_signoff": "Retain evidence supporting control effectiveness, testing/UAT, release notes and formal sign-off or workflow approval for relevant runs or changes.",
    "resilience": "Evidence backup/recovery, restore testing where required, fallback/BCP steps, deputy cover and SPOF mitigation for critical/time-sensitive EUCs.",
}

BASELINE_CONTROL_LABELS = {
    "registration_risk_assessment": "Registration & risk assessment",
    "privileged_access": "Privileged Access",
    "versioning_change_log": "Versioning & change log",
    "checks_reconciliations": "Checks & reconciliations",
    "library_controls_cacrt": "EUC Library of Controls / CACRT",
    "operating_procedure": "Operating Procedure",
    "evidence_signoff": "Evidence & sign-off",
    "resilience": "Resilience",
}

CONTROL_STATUS_RANK = {"Not in place": 0, "Partially in place": 1, "In place and evidenced": 2, "N/A": 1}


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


def registration_control_readiness(euc_id: int | None, include_assessment_id: int | None = None) -> dict[str, Any]:
    """Return readiness for the Registration & Risk Assessment baseline control.

    The control is not fully in place merely because the owner has submitted an
    assessment. It requires a complete EUC registration/mapping and an Accepted
    risk assessment. `include_assessment_id` is used during reviewer acceptance
    so the accepted assessment itself can satisfy the condition.
    """
    if not euc_id:
        return {
            "registration_complete": False,
            "accepted_risk_assessment": False,
            "allowed_status": "Not in place",
            "missing_items": ["EUC record"],
        }

    euc = fetch_one("SELECT * FROM eucs WHERE euc_id = ?", (euc_id,))
    if not euc:
        return {
            "registration_complete": False,
            "accepted_risk_assessment": False,
            "allowed_status": "Not in place",
            "missing_items": ["EUC record"],
        }

    required_fields = {
        "name": "EUC name",
        "owner": "Owner",
        "business_unit": "Business unit",
        "technology_type": "Technology type",
        "storage_location": "Storage location",
        "bcbs239_output_mapping": "Primary BCBS 239 output mapping",
    }
    missing = [label for field, label in required_fields.items() if not str(euc.get(field) or "").strip()]
    mapping_value = str(euc.get("bcbs239_output_mapping") or "").strip().lower()
    if mapping_value in {"n/a", "na", "not applicable"}:
        missing.append("Primary BCBS 239 output mapping cannot be Not Applicable")

    if include_assessment_id:
        accepted = fetch_one(
            """
            SELECT assessment_id FROM risk_assessments
            WHERE euc_id = ? AND (status = 'Accepted' OR assessment_id = ?)
            LIMIT 1
            """,
            (euc_id, include_assessment_id),
        )
    else:
        accepted = fetch_one(
            "SELECT assessment_id FROM risk_assessments WHERE euc_id = ? AND status = 'Accepted' LIMIT 1",
            (euc_id,),
        )

    registration_complete = not missing
    accepted_risk_assessment = bool(accepted)
    if registration_complete and accepted_risk_assessment:
        allowed = "In place and evidenced"
    elif registration_complete or accepted_risk_assessment:
        allowed = "Partially in place"
    else:
        allowed = "Partially in place" if euc else "Not in place"

    return {
        "registration_complete": registration_complete,
        "accepted_risk_assessment": accepted_risk_assessment,
        "allowed_status": allowed,
        "missing_items": sorted(set(missing)),
    }


def _cap_control_status(selected_status: str | None, allowed_status: str) -> str:
    selected = selected_status or "Partially in place"
    if selected == "N/A":
        selected = "Partially in place"
    selected_rank = CONTROL_STATUS_RANK.get(selected, 1)
    allowed_rank = CONTROL_STATUS_RANK.get(allowed_status, 1)
    if selected_rank <= allowed_rank:
        return selected
    for status, rank in CONTROL_STATUS_RANK.items():
        if rank == allowed_rank and status != "N/A":
            return status
    return allowed_status


def effective_registration_control_status(payload: dict[str, Any]) -> str:
    selected = payload.get("control_registration_risk_assessment") or "Partially in place"
    euc_id = payload.get("euc_id")
    status = payload.get("status")
    assessment_id = payload.get("assessment_id")
    include_assessment_id = int(assessment_id) if status == "Accepted" and assessment_id else None
    readiness = registration_control_readiness(int(euc_id), include_assessment_id) if euc_id else {"allowed_status": "Partially in place"}
    return _cap_control_status(selected, readiness["allowed_status"])


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
    # Registration & Risk Assessment has a governance readiness guard: it can
    # only be effective as "In place and evidenced" once registration/mapping is
    # complete and the risk assessment has been independently accepted.
    controls["registration_risk_assessment"] = effective_registration_control_status(payload)
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
        "effective_registration_risk_assessment_control": controls["registration_risk_assessment"],
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


def _normalize_match_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def detect_duplicates(name: str, owner: str, business_unit: str, storage_location: str, exclude_euc_id: int | None = None) -> pd.DataFrame:
    """High-confidence duplicate detection for EUC registration.

    The previous heuristic flagged any EUC in the same business unit or with the
    same owner, which generated false positives for normal portfolio activity.
    The revised logic only reports records with a strong name match, matching
    storage path, or similar name combined with the same owner/business unit.
    """
    params: list[Any] = []
    sql = """
        SELECT euc_id, reference_id, name, owner, business_unit, storage_location, lifecycle_status, residual_risk
        FROM eucs
    """
    if exclude_euc_id:
        sql += " WHERE euc_id <> ?"
        params.append(exclude_euc_id)
    sql += " ORDER BY updated_at DESC"
    df = dataframe(sql, tuple(params))
    if df.empty:
        return df

    target_name = _normalize_match_text(name)
    target_owner = _normalize_match_text(owner)
    target_unit = _normalize_match_text(business_unit)
    target_storage = _normalize_match_text(storage_location)

    matches: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        row_name = _normalize_match_text(row.get("name"))
        row_owner = _normalize_match_text(row.get("owner"))
        row_unit = _normalize_match_text(row.get("business_unit"))
        row_storage = _normalize_match_text(row.get("storage_location"))
        reasons: list[str] = []
        confidence = ""

        if target_name and row_name == target_name:
            reasons.append("same EUC name")
            confidence = "High"

        similarity = SequenceMatcher(None, target_name, row_name).ratio() if target_name and row_name else 0.0
        if similarity >= 0.88:
            reasons.append(f"very similar EUC name ({similarity:.0%})")
            confidence = "High"
        elif similarity >= 0.72 and ((target_owner and target_owner == row_owner) or (target_unit and target_unit == row_unit)):
            reasons.append(f"similar EUC name ({similarity:.0%}) with same owner/business unit")
            confidence = confidence or "Medium"

        if target_storage and row_storage and target_storage == row_storage:
            reasons.append("same controlled storage location")
            confidence = "High"

        if reasons:
            item = row.to_dict()
            item["duplicate_confidence"] = confidence or "Medium"
            item["match_reason"] = "; ".join(dict.fromkeys(reasons))
            matches.append(item)

    return pd.DataFrame(matches)


def validate_mapping_fields(payload: dict[str, Any]) -> list[str]:
    errors = []
    primary_mapping = str(payload.get("bcbs239_output_mapping") or "").strip()
    if not primary_mapping:
        errors.append("BCBS 239 output mapping is required.")
    if primary_mapping.lower() in {"n/a", "na", "not applicable"}:
        errors.append("Primary BCBS 239 output mapping cannot be Not Applicable. Select a mapped output from the controlled list.")
    mapping_fields = ["bcbs239_output_mapping", "inputs", "outputs", "recipients", "dependencies"]
    has_na = any(str(payload.get(field, "")).strip().lower() == "not applicable" for field in mapping_fields)
    if has_na and not payload.get("mapping_na_justification"):
        errors.append("A justification is required when a mapping field is marked Not Applicable.")
    return errors


def create_euc(payload: dict[str, Any], username: str) -> int:
    mandatory = ["name", "legal_entity", "owner", "business_unit", "technology_type", "storage_location", "bcbs239_output_mapping"]
    missing = [field for field in mandatory if not str(payload.get(field, "")).strip()]
    errors = [f"Missing mandatory field: {field}" for field in missing] + validate_mapping_fields(payload)
    if errors:
        raise ValueError("\n".join(errors))

    now = utc_now()
    reference_id = generate_reference_id()
    euc_fields = [
        "reference_id", "name", "description", "purpose", "legal_entity", "owner", "owner_delegate", "reviewer",
        "business_unit", "technology_type", "storage_location", "frequency", "schedule", "cut_off", "business_context",
        "supports_material_report", "supports_material_kri", "supports_material_model", "multi_bu_use", "active_user_count",
        "created_by_bu", "acquired_third_party_cots", "support_contract_sla", "last_risk_assessment_date",
        "bcbs239_output_mapping", "cde_linkage", "inputs", "outputs", "recipients", "dependencies", "spof_indicator",
        "inherent_risk", "residual_risk", "overall_status", "documentation_completeness_status", "lifecycle_status",
        "next_review_date", "industrialization_rationale", "decommissioning_rationale", "created_by", "created_at", "updated_at",
        "mapping_na_justification", "onboarding_type", "design_logic_applicable", "design_logic_rationale",
        "euc_operationalization_document_link", "policy242_operationalization_link", "bcbs239_elevated_inherent_override",
        "backup_path_documented", "last_restore_drill_date", "deputy_cover", "knowledge_transfer_evidence",
        "critical_dependencies_documented",
        "registration_date", "go_live_date", "materiality_criterion_1", "materiality_criterion_2", "materiality_criterion_3",
        "material_report_mapping", "material_kri_mapping", "material_model_mapping", "evidence_pack_location",
        "library_controls_link", "risk_assessment_link", "baseline_controls_complete", "four_eye_review_required",
        "high_criticality_evidence_pack_required", "access_control_evidence_status", "reconciliation_control_evidence_status",
        "testing_evidence_status", "uat_evidence_status", "approval_signoff_evidence_status",
        "documentation_gap_assessment_required", "documentation_gaps_summary", "remediation_action_owner",
        "remediation_target_date", "incident_near_miss_count", "last_incident_date", "material_mapping_confidence",
        "migration_status", "migration_notes", "legacy_sensitive_data_flag", "legacy_criticality",

    ]
    values_by_field = {
        **payload,
        "reference_id": reference_id,
        "spof_indicator": payload.get("spof_indicator", "No"),
        "inherent_risk": payload.get("inherent_risk", "Medium"),
        "residual_risk": payload.get("residual_risk", "Medium"),
        "overall_status": payload.get("overall_status", "Registered"),
        "documentation_completeness_status": "Not Checked",
        "lifecycle_status": payload.get("lifecycle_status", "Registered"),
        "created_by": username,
        "created_at": now,
        "updated_at": now,
        "onboarding_type": payload.get("onboarding_type", "New EUC"),
        "design_logic_applicable": payload.get("design_logic_applicable", "No"),
        "bcbs239_elevated_inherent_override": "Yes" if any(str(payload.get(col) or "").strip().lower() == "yes" for col in ("supports_material_report", "supports_material_kri", "supports_material_model")) else "No",
    }
    placeholders = ", ".join("?" for _ in euc_fields)
    euc_id = execute(
        f"INSERT INTO eucs({', '.join(euc_fields)}) VALUES ({placeholders})",
        tuple(values_by_field.get(field) for field in euc_fields),
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
    queue_raci_notifications(
        "EUC_REGISTERED",
        "EUC",
        euc_id,
        euc_id,
        username,
        context={"Reference ID": reference_id, "Owner": payload.get("owner"), "Business unit": payload.get("business_unit")},
    )
    return euc_id

def update_euc(euc_id: int, payload: dict[str, Any], username: str) -> None:
    old = get_euc(euc_id)
    if not old:
        raise ValueError("EUC not found")
    errors = validate_mapping_fields(payload)
    if errors:
        raise ValueError("\n".join(errors))
    if any(str(payload.get(col, old.get(col)) or "").strip().lower() == "yes" for col in ("supports_material_report", "supports_material_kri", "supports_material_model")):
        payload["bcbs239_elevated_inherent_override"] = "Yes"
    elif any(col in payload for col in ("supports_material_report", "supports_material_kri", "supports_material_model")):
        payload["bcbs239_elevated_inherent_override"] = "No"

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
        "supports_material_report",
        "supports_material_kri",
        "supports_material_model",
        "multi_bu_use",
        "active_user_count",
        "created_by_bu",
        "acquired_third_party_cots",
        "support_contract_sla",
        "last_risk_assessment_date",
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
        "onboarding_type",
        "design_logic_applicable",
        "design_logic_rationale",
        "euc_operationalization_document_link",
        "policy242_operationalization_link",
        "bcbs239_elevated_inherent_override",
        "backup_path_documented",
        "last_restore_drill_date",
        "deputy_cover",
        "knowledge_transfer_evidence",
        "critical_dependencies_documented",
        "registration_date", "go_live_date", "materiality_criterion_1", "materiality_criterion_2", "materiality_criterion_3",
        "material_report_mapping", "material_kri_mapping", "material_model_mapping", "evidence_pack_location",
        "library_controls_link", "risk_assessment_link", "baseline_controls_complete", "four_eye_review_required",
        "high_criticality_evidence_pack_required", "access_control_evidence_status", "reconciliation_control_evidence_status",
        "testing_evidence_status", "uat_evidence_status", "approval_signoff_evidence_status",
        "documentation_gap_assessment_required", "documentation_gaps_summary", "remediation_action_owner",
        "remediation_target_date", "incident_near_miss_count", "last_incident_date", "material_mapping_confidence",
        "migration_status", "migration_notes", "legacy_sensitive_data_flag", "legacy_criticality",

    ]
    assignments = ", ".join([f"{field} = ?" for field in allowed_fields])
    values = [payload.get(field, old.get(field)) for field in allowed_fields]
    values.extend([utc_now(), euc_id])
    execute(f"UPDATE eucs SET {assignments}, updated_at = ? WHERE euc_id = ?", tuple(values))
    insert_audit("EUC", euc_id, "UPDATE", username, old, payload)
    queue_raci_notifications(
        "EUC_UPDATED",
        "EUC",
        euc_id,
        euc_id,
        username,
        context={"Updated fields": ", ".join(sorted(payload.keys())) if isinstance(payload, dict) else "EUC record"},
    )


def update_euc_status(euc_id: int, lifecycle_status: str, username: str, overall_status: str | None = None) -> None:
    old = get_euc(euc_id)
    execute(
        "UPDATE eucs SET lifecycle_status = ?, overall_status = ?, updated_at = ? WHERE euc_id = ?",
        (lifecycle_status, overall_status or lifecycle_status, utc_now(), euc_id),
    )
    insert_audit("EUC", euc_id, "STATUS_TRANSITION", username, old, {"lifecycle_status": lifecycle_status})
    if lifecycle_status == "Industrialization Candidate":
        queue_raci_notifications("INDUSTRIALIZATION_REQUESTED", "EUC", euc_id, euc_id, username, context={"Lifecycle status": lifecycle_status})


def get_components(euc_id: int) -> pd.DataFrame:
    return dataframe(
        """
        SELECT c.*, e.reference_id AS parent_reference_id, e.name AS euc_application, e.business_unit AS parent_business_unit
        FROM components c
        JOIN eucs e ON e.euc_id = c.euc_id
        WHERE c.euc_id = ?
        ORDER BY c.component_id
        """,
        (euc_id,),
    )


def get_component(component_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT c.*, e.reference_id AS parent_reference_id, e.name AS euc_application, e.business_unit AS parent_business_unit
        FROM components c
        JOIN eucs e ON e.euc_id = c.euc_id
        WHERE c.component_id = ?
        """,
        (component_id,),
    )


COMPONENT_FIELDS = [
    "euc_id", "component_name", "component_type", "technology", "storage_location", "description", "criticality", "owner",
    "rrf_mapping", "operationalization_document_link", "file_description", "technology_type", "controlled_storage_type",
    "controlled_storage_location", "input_sources", "asset_cut_off", "processing_schedule", "execution_frequency",
    "cde_mappings", "data_outputs", "level_of_automation", "backup_recovery_arrangements", "spof_risk",
    "modification_date", "review_date",
    "cots_third_party_component", "vendor_tool_name", "asset_support_contract_sla", "vendor_support_status",
    "end_of_support_date", "approved_corporate_environment", "personal_byod_storage_used",
    "required_input_availability_time", "expected_run_duration", "timeliness_monitoring_performed",
    "fallback_bcp_steps_link", "asset_last_restore_test_date", "asset_deputy_cover", "key_person_dependency_mitigated",
    "version_release_identifier", "change_log_link", "latest_release_notes_link", "retention_evidence_location",
    "data_classification", "external_sharing", "material_mapping_confidence", "asset_migration_status",
    "asset_migration_notes", "legacy_sensitive_data_flag", "legacy_criticality", "legacy_support_contract_sla",

]


def _component_insert_payload(payload: dict[str, Any]) -> dict[str, Any]:
    technology_type = payload.get("technology_type") or payload.get("component_type") or payload.get("technology") or "Other"
    storage_location = payload.get("controlled_storage_location") or payload.get("storage_location")
    file_description = payload.get("file_description") or payload.get("description")
    return {
        **payload,
        "component_name": payload.get("component_name") or payload.get("asset_name"),
        "component_type": payload.get("component_type") or technology_type or "Other",
        "technology": payload.get("technology") or technology_type,
        "storage_location": payload.get("storage_location") or storage_location,
        "description": payload.get("description") or file_description,
        "file_description": file_description,
        "technology_type": technology_type,
        "controlled_storage_location": storage_location,
    }


def create_component(payload: dict[str, Any], username: str) -> int:
    now = utc_now()
    payload = _component_insert_payload(payload)
    if not str(payload.get("component_name") or "").strip():
        raise ValueError("Asset / file name is required.")
    fields = COMPONENT_FIELDS + ["created_at"]
    values_by_field = {**payload, "created_at": now}
    component_id = execute(
        f"INSERT INTO components({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(values_by_field.get(field) for field in fields),
    )
    insert_audit("Component", component_id, "CREATE", username, None, payload)
    queue_raci_notifications(
        "EUC_COMPONENT_UPDATED",
        "Component",
        component_id,
        payload.get("euc_id"),
        username,
        context={"Component": payload.get("component_name"), "Action": "Created"},
    )
    return component_id


def update_component(component_id: int, payload: dict[str, Any], username: str) -> None:
    old = get_component(component_id)
    if not old:
        raise ValueError("Component not found")
    payload = _component_insert_payload(payload)
    if not str(payload.get("component_name") or old.get("component_name") or "").strip():
        raise ValueError("Asset / file name is required.")
    allowed_fields = [field for field in COMPONENT_FIELDS if field != "euc_id"]
    assignments = ", ".join([f"{field} = ?" for field in allowed_fields])
    values = [payload.get(field, old.get(field)) for field in allowed_fields]
    values.append(component_id)
    execute(f"UPDATE components SET {assignments} WHERE component_id = ?", tuple(values))
    insert_audit("Component", component_id, "UPDATE", username, old, payload)
    queue_raci_notifications("EUC_COMPONENT_UPDATED", "Component", component_id, old.get("euc_id"), username, context={"Component": payload.get("component_name", old.get("component_name"))})

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
            rationale, trigger_type, version, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            payload.get("status", "Submitted"),
            now,
        ),
    )
    lifecycle = "Awaiting Documentation" if residual_risk in {"Low", "Medium", "High", "Very High"} else "Registered"
    execute(
        """
        UPDATE eucs
        SET inherent_risk = ?, residual_risk = ?, lifecycle_status = ?, overall_status = ?,
            last_risk_assessment_date = ?, updated_at = ?
        WHERE euc_id = ?
        """,
        (inherent_risk, residual_risk, lifecycle, lifecycle, payload.get("assessment_date", date.today().isoformat()), utc_now(), payload["euc_id"]),
    )
    insert_audit("Risk Assessment", assessment_id, "CREATE", username, None, {**payload, **calculated, "inherent_risk": inherent_risk, "residual_risk": residual_risk})
    queue_raci_notifications(
        "RISK_ASSESSMENT_COMPLETED",
        "Risk Assessment",
        assessment_id,
        payload["euc_id"],
        username,
        context={"Overall inherent risk": inherent_risk, "Overall residual risk": residual_risk, "Version": version},
    )
    evaluate_and_update_completeness(payload["euc_id"], username, create_missing_tasks=True)
    auto_close_tasks_for_risk_assessment(payload["euc_id"], assessment_id, username)
    return assessment_id


def latest_risk_assessment(euc_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT * FROM risk_assessments
        WHERE euc_id = ?
        ORDER BY version DESC, assessment_id DESC
        LIMIT 1
        """,
        (euc_id,),
    )


def recalculate_risk_assessment(assessment_id: int, username: str = "system", write_audit: bool = True) -> dict[str, Any]:
    """Recalculate an existing Excel-aligned assessment after review status changes.

    This is primarily used when a reviewer accepts an assessment: the
    Registration & Risk Assessment baseline control may then become effective
    as "In place and evidenced" if the EUC registration/mapping is complete.
    """
    row = fetch_one("SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,))
    if not row:
        raise ValueError("Risk assessment not found.")
    calculated = calculate_excel_risk_assessment(row)
    inherent_risk = calculated["overall_inherent_risk"]
    residual_risk = calculated["overall_residual_risk"]
    effect_rank = {"Strong": 1, "Adequate": 2, "Weak": 3, "Not in place": 4}
    control_effectiveness_score = max(
        effect_rank[calculated["integrity_control_effectiveness"]],
        effect_rank[calculated["timeliness_control_effectiveness"]],
    )
    old_snapshot = dict(row)
    execute(
        """
        UPDATE risk_assessments
        SET integrity_accuracy_score = ?, timeliness_availability_score = ?, business_criticality_score = ?,
            control_effectiveness_score = ?, inherent_risk = ?, residual_risk = ?,
            materially_supports_bcbs239 = ?, effective_integrity_inherent = ?, effective_timeliness_inherent = ?,
            integrity_control_effectiveness = ?, timeliness_control_effectiveness = ?,
            integrity_residual_risk = ?, timeliness_residual_risk = ?, overall_inherent_risk = ?,
            overall_residual_risk = ?, required_action = ?
        WHERE assessment_id = ?
        """,
        (
            _risk_score(calculated["owner_integrity_inherent"]),
            _risk_score(calculated["owner_timeliness_inherent"]),
            _risk_score(inherent_risk),
            control_effectiveness_score,
            inherent_risk,
            residual_risk,
            calculated["materially_supports_bcbs239"],
            calculated["effective_integrity_inherent"],
            calculated["effective_timeliness_inherent"],
            calculated["integrity_control_effectiveness"],
            calculated["timeliness_control_effectiveness"],
            calculated["integrity_residual_risk"],
            calculated["timeliness_residual_risk"],
            calculated["overall_inherent_risk"],
            calculated["overall_residual_risk"],
            calculated["required_action"],
            assessment_id,
        ),
    )
    latest = latest_risk_assessment(int(row["euc_id"]))
    if latest and int(latest["assessment_id"]) == int(assessment_id):
        execute(
            "UPDATE eucs SET inherent_risk = ?, residual_risk = ?, last_risk_assessment_date = ?, updated_at = ? WHERE euc_id = ?",
            (inherent_risk, residual_risk, row.get("assessment_date"), utc_now(), row["euc_id"]),
        )
    if write_audit:
        insert_audit("Risk Assessment", assessment_id, "RECALCULATE", username, old_snapshot, calculated)
    return calculated


def review_risk_assessment(assessment_id: int, status: str, comments: str, username: str) -> None:
    old = fetch_one("SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,))
    if not old:
        raise ValueError("Risk assessment not found.")
    if status not in {"Submitted", "Accepted", "Rejected"}:
        raise ValueError("Invalid risk assessment status.")
    execute(
        """
        UPDATE risk_assessments
        SET status = ?, reviewed_by = ?, reviewed_at = ?, review_comments = ?
        WHERE assessment_id = ?
        """,
        (status, username, utc_now(), comments, assessment_id),
    )
    # Recalculate after the review status update. Once Accepted, this assessment
    # can satisfy the Registration & Risk Assessment control if registration is complete.
    recalculate_risk_assessment(assessment_id, username, write_audit=False)
    insert_audit("Risk Assessment", assessment_id, "REVIEW", username, old, {"status": status, "comments": comments})
    queue_raci_notifications(
        "RISK_ASSESSMENT_REVIEWED",
        "Risk Assessment",
        assessment_id,
        old["euc_id"],
        username,
        context={"Review status": status, "Comments": comments},
    )
    if status == "Rejected":
        euc = get_euc(old["euc_id"])
        create_task(
            euc_id=old["euc_id"],
            task_type="Reassessment",
            title=f"Revise rejected risk assessment #{assessment_id}",
            description=comments or "Risk assessment was returned by reviewer and must be updated.",
            assigned_to=euc.get("owner") if euc else None,
            assigned_role=OWNER_ROLE,
            due_date=add_days(DEFAULT_DUE_DAYS["Reassessment"]),
            priority="High",
            username=username,
        )
    evaluate_and_update_completeness(old["euc_id"], username, create_missing_tasks=True)


def risk_assessment_edit_can_be_approved_by(role: str) -> bool:
    return role in {GCC_ROLE, DVU_ROLE}


def request_risk_assessment_edit(assessment_id: int, reason: str, username: str) -> None:
    old = fetch_one("SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,))
    if not old:
        raise ValueError("Risk assessment not found.")
    if old.get("status") not in {"Submitted", "Accepted", "Rejected"}:
        raise ValueError("Risk assessment has an invalid status.")
    execute(
        """
        UPDATE risk_assessments
        SET edit_request_status = 'Pending', edit_requested_by = ?, edit_requested_at = ?,
            edit_request_reason = ?, edit_approved_by = NULL, edit_approved_at = NULL,
            edit_approval_comments = NULL
        WHERE assessment_id = ?
        """,
        (username, utc_now(), reason, assessment_id),
    )
    insert_audit("Risk Assessment", assessment_id, "EDIT_REQUEST", username, old, {"reason": reason})
    queue_raci_notifications(
        "RISK_ASSESSMENT_EDIT_REQUESTED",
        "Risk Assessment",
        assessment_id,
        old["euc_id"],
        username,
        context={"Edit request reason": reason},
    )


def decide_risk_assessment_edit_request(assessment_id: int, decision: str, comments: str, username: str) -> None:
    old = fetch_one("SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,))
    if not old:
        raise ValueError("Risk assessment not found.")
    if decision not in {"Approved", "Rejected"}:
        raise ValueError("Invalid edit-request decision.")
    execute(
        """
        UPDATE risk_assessments
        SET edit_request_status = ?, edit_approved_by = ?, edit_approved_at = ?, edit_approval_comments = ?
        WHERE assessment_id = ?
        """,
        (decision, username, utc_now(), comments, assessment_id),
    )
    insert_audit("Risk Assessment", assessment_id, "EDIT_REQUEST_DECISION", username, old, {"decision": decision, "comments": comments})
    queue_raci_notifications(
        "RISK_ASSESSMENT_EDIT_REQUEST_DECIDED",
        "Risk Assessment",
        assessment_id,
        old["euc_id"],
        username,
        context={"Decision": decision, "Comments": comments},
    )


def update_risk_assessment_in_place(assessment_id: int, payload: dict[str, Any], username: str) -> None:
    old = fetch_one("SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,))
    if not old:
        raise ValueError("Risk assessment not found.")
    if old.get("edit_request_status") != "Approved":
        raise PermissionError("Risk assessment edits require prior approval by GCC or Data Validation.")
    payload = {**old, **payload, "assessment_id": assessment_id, "status": "Submitted"}
    calculated = calculate_excel_risk_assessment(payload)
    inherent_risk = calculated["overall_inherent_risk"]
    residual_risk = calculated["overall_residual_risk"]
    effect_rank = {"Strong": 1, "Adequate": 2, "Weak": 3, "Not in place": 4}
    control_effectiveness_score = max(
        effect_rank[calculated["integrity_control_effectiveness"]],
        effect_rank[calculated["timeliness_control_effectiveness"]],
    )
    now = utc_now()
    execute(
        """
        UPDATE risk_assessments
        SET assessment_date = ?, assessed_by = ?, integrity_accuracy_score = ?, timeliness_availability_score = ?,
            complexity_score = ?, business_criticality_score = ?, control_effectiveness_score = ?,
            inherent_risk = ?, residual_risk = ?, materiality_q1 = ?, materiality_q2 = ?, materiality_q3 = ?,
            materially_supports_bcbs239 = ?, owner_integrity_inherent = ?, owner_timeliness_inherent = ?,
            effective_integrity_inherent = ?, effective_timeliness_inherent = ?, integrity_control_effectiveness = ?,
            timeliness_control_effectiveness = ?, integrity_residual_risk = ?, timeliness_residual_risk = ?,
            overall_inherent_risk = ?, overall_residual_risk = ?, required_action = ?,
            control_registration_risk_assessment = ?, control_privileged_access = ?, control_versioning_change_log = ?,
            control_checks_reconciliations = ?, control_library_controls_cacrt = ?, control_operating_procedure = ?,
            control_evidence_signoff = ?, control_resilience = ?, rationale = ?, trigger_type = ?,
            status = 'Submitted', reviewed_by = NULL, reviewed_at = NULL, review_comments = NULL,
            edit_request_status = 'Completed', last_edited_by = ?, last_edited_at = ?
        WHERE assessment_id = ?
        """,
        (
            payload.get("assessment_date", date.today().isoformat()),
            payload.get("assessed_by", username),
            _risk_score(calculated["owner_integrity_inherent"]),
            _risk_score(calculated["owner_timeliness_inherent"]),
            int(payload.get("complexity_score") or old.get("complexity_score") or 1),
            _risk_score(inherent_risk),
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
            payload.get("trigger_type", old.get("trigger_type") or "Periodic"),
            username,
            now,
            assessment_id,
        ),
    )
    latest = latest_risk_assessment(int(old["euc_id"]))
    if latest and int(latest["assessment_id"]) == int(assessment_id):
        execute(
            "UPDATE eucs SET inherent_risk = ?, residual_risk = ?, lifecycle_status = ?, overall_status = ?, last_risk_assessment_date = ?, updated_at = ? WHERE euc_id = ?",
            (inherent_risk, residual_risk, "Awaiting Documentation", "Awaiting Documentation", payload.get("assessment_date"), utc_now(), old["euc_id"]),
        )
    insert_audit("Risk Assessment", assessment_id, "EDIT", username, old, {**payload, **calculated, "status": "Submitted"})
    queue_raci_notifications(
        "RISK_ASSESSMENT_EDITED",
        "Risk Assessment",
        assessment_id,
        old["euc_id"],
        username,
        context={"Overall inherent risk": inherent_risk, "Overall residual risk": residual_risk, "Status": "Submitted"},
    )
    evaluate_and_update_completeness(old["euc_id"], username, create_missing_tasks=True)


def safe_filename(filename: str) -> str:
    stem = Path(filename).stem[:80]
    suffix = Path(filename).suffix[:20]
    clean_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "document"
    return f"{clean_stem}{suffix}"


def save_document_file(euc_id: int, original_name: str, file_bytes: bytes) -> tuple[str, str]:
    euc_folder = UPLOAD_PATH / f"euc_{euc_id}"
    euc_folder.mkdir(parents=True, exist_ok=True)
    # Include microseconds and a short UUID segment so simultaneous uploads with
    # the same original filename never overwrite each other.
    file_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex[:8]}_{safe_filename(original_name)}"
    file_path = euc_folder / file_name
    with open(file_path, "wb") as fh:
        fh.write(file_bytes)
    return file_name, str(file_path.relative_to(UPLOAD_PATH.parent))


def create_document_record(payload: dict[str, Any], username: str) -> int:
    payload = dict(payload)
    payload["document_type"] = canonical_document_type(payload.get("document_type")) or payload.get("document_type")
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
    queue_raci_notifications(
        "EVIDENCE_SUBMITTED",
        "Document",
        document_id,
        payload["euc_id"],
        username,
        context={"Document type": payload.get("document_type"), "Status": payload.get("status", "Submitted")},
    )
    evaluate_and_update_completeness(payload["euc_id"], username, create_missing_tasks=False)
    auto_close_tasks_for_document_submission(payload["euc_id"], document_id, payload.get("document_type"), username)
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
    queue_raci_notifications(
        "EVIDENCE_REVIEWED",
        "Document",
        document_id,
        old["euc_id"],
        username,
        context={"Document type": old.get("document_type"), "Review status": status, "Deficiency": deficiency_tag},
    )
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
    elif status == "Accepted":
        auto_close_tasks_for_document_submission(old["euc_id"], document_id, old.get("document_type"), username)
    evaluate_and_update_completeness(old["euc_id"], username, create_missing_tasks=True)


def _default_rule_metadata(doc_type: str) -> tuple[str, str]:
    """Return control area and CACRT dimension for a required artifact."""
    doc_type = canonical_document_type(doc_type) or str(doc_type or "")
    if doc_type == "Operating Procedure":
        return "Ownership & Accountability", "Traceability"
    if doc_type in {"Library of Controls", "Control Evidence"}:
        return "Reconciliation & Controls", "Completeness"
    if doc_type in {"Testing Evidence", "UAT Evidence", "Design / Logic Evidence"}:
        return "Data Validation", "Accuracy"
    if doc_type == "Reconciliation Evidence":
        return "Reconciliation & Controls", "Reasonableness"
    if doc_type == "Resilience Evidence":
        return "Operational Resilience", "Timeliness"
    if doc_type == "Change & Versioning Evidence":
        return "Change Management", "Consistency"
    if doc_type in {"Access Review Evidence", "Access Revocation Evidence"}:
        return "Access Control", "Traceability"
    if doc_type in {"Exception Record", "Incident & RCA Evidence"}:
        return "Issue Management", "Traceability"
    if doc_type in {"Decommissioning Evidence", "Archive Evidence"}:
        return "Decommissioning", "Traceability"
    if doc_type in {"Approval Evidence", "Review Evidence", "Industrialization Assessment Evidence"}:
        return "Ownership & Accountability", "Traceability"
    return "Ownership & Accountability", "Completeness"


def seed_required_rules(username: str = "system") -> None:
    """Seed or top-up approved artifact rules based on the current policy baseline."""
    for risk, docs in DEFAULT_REQUIRED_ARTIFACTS.items():
        for doc_type in docs:
            canonical = canonical_document_type(doc_type)
            if not canonical:
                continue
            existing = fetch_one(
                """
                SELECT rule_id FROM required_artifact_rules
                WHERE risk_level = ? AND required_document_type = ? AND lifecycle_stage = 'Active'
                LIMIT 1
                """,
                (risk, canonical),
            )
            if existing:
                continue
            control_area, cacrt_dimension = _default_rule_metadata(canonical)
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
                    canonical,
                    control_area,
                    cacrt_dimension,
                    1,
                    "Default policy baseline rule loaded during initialization. Risk level refers to Overall Inherent Risk.",
                    username,
                    username,
                    "Approved",
                ),
            )


def _latest_assessment_row(euc_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT * FROM risk_assessments
        WHERE euc_id = ?
        ORDER BY version DESC, assessment_id DESC
        LIMIT 1
        """,
        (euc_id,),
    )


def _is_material_bcbs_assessment(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    if str(row.get("materially_supports_bcbs239") or "").strip().lower() == "yes":
        return True
    return any(str(row.get(col) or "").strip().lower() == "yes" for col in ("materiality_q1", "materiality_q2", "materiality_q3"))


def inherent_baseline_for_euc(euc_id: int) -> dict[str, Any]:
    """Determine the policy baseline for evidence requirements."""
    euc = get_euc(euc_id)
    if not euc:
        return {"baseline_risk": "Medium", "material_bcbs239": False, "source": "default", "assessment_id": None}
    latest = _latest_assessment_row(euc_id)
    material = _is_material_bcbs_assessment(latest) or any(
        str(euc.get(col) or "").strip().lower() == "yes"
        for col in ("supports_material_report", "supports_material_kri", "supports_material_model")
    )
    candidates = [euc.get("inherent_risk") or "Medium"]
    if latest:
        candidates.append(latest.get("overall_inherent_risk") or latest.get("inherent_risk") or "Medium")
    baseline = "Very High" if material else _max_risk(candidates)
    return {
        "baseline_risk": baseline,
        "material_bcbs239": material,
        "source": "BCBS 239 materiality override" if material else "Overall Inherent Risk",
        "assessment_id": latest.get("assessment_id") if latest else None,
    }


def _append_requirement(
    rows: list[dict[str, Any]],
    seen: set[str],
    risk_level: str,
    lifecycle_stage: str | None,
    doc_type: str,
    reason: str,
    mandatory: bool = True,
    classification: str = "Mandatory baseline",
    trigger: str = "Inherent risk baseline",
) -> None:
    canonical = canonical_document_type(doc_type)
    if not canonical or canonical in seen:
        return
    control_area, cacrt_dimension = _default_rule_metadata(canonical)
    rows.append(
        {
            "risk_level": risk_level,
            "risk_basis": "Overall Inherent Risk",
            "lifecycle_stage": lifecycle_stage or "Active",
            "required_document_type": canonical,
            "control_area": control_area,
            "cacrt_dimension": cacrt_dimension,
            "mandatory_flag": int(bool(mandatory)),
            "requirement_classification": classification,
            "trigger": trigger,
            "requirement_reason": reason,
        }
    )
    seen.add(canonical)


def _is_yes(value: Any) -> bool:
    return str(value or "").strip().lower() == "yes"


def _is_legacy_euc(euc: dict[str, Any]) -> bool:
    val = str(euc.get("onboarding_type") or euc.get("legacy_onboarding") or "").strip().lower()
    return val in {"legacy", "legacy euc", "1", "true", "yes"}


def _event_overlay_requirements(euc: dict[str, Any], baseline_risk: str) -> list[tuple[str, str, str, bool, str, str]]:
    """Return additional requirements driven by lifecycle events/states.

    Tuple: (document_type, lifecycle_stage, reason, mandatory, classification, trigger)
    """
    euc_id = int(euc["euc_id"])
    overlays: list[tuple[str, str, str, bool, str, str]] = []
    spof = _is_yes(euc.get("spof_indicator"))
    lifecycle = euc.get("lifecycle_status") or "Active"
    high_or_very_high = _risk_score(baseline_risk) >= _risk_score("High")
    is_legacy = _is_legacy_euc(euc)

    if _is_yes(euc.get("design_logic_applicable")):
        overlays.append((
            "Design / Logic Evidence",
            lifecycle,
            "EUC contains material business logic, automation, complex calculations, scripts, macros, transformations, critical assumptions or mappings not readily understood through the Operating Procedure alone.",
            True,
            "Where applicable",
            "Design / logic applicability",
        ))

    if spof:
        overlays.append(("Resilience Evidence", lifecycle, "SPOF indicator is Yes; backup, fallback, dependency and deputy-cover evidence is required.", True, "Conditional mandatory", "SPOF"))

    # New EUCs need go-live assurance. Legacy EUCs do not recreate historical testing/UAT/approval solely for initial onboarding.
    if not is_legacy and lifecycle in {"Draft", "Submitted", "Registered", "Awaiting Documentation", "Review Ready"}:
        overlays.extend([
            ("Testing Evidence", "New EUC Go-Live", "New EUC onboarding requires testing evidence before go-live, proportionate to risk and complexity.", True, "Conditional mandatory", "New EUC go-live"),
            ("UAT Evidence", "New EUC Go-Live", "New EUC onboarding requires UAT / user acceptance evidence before go-live.", True, "Conditional mandatory", "New EUC go-live"),
            ("Approval Evidence", "New EUC Go-Live", "New EUC onboarding requires formal go-live/sign-off evidence before BAU use.", True, "Conditional mandatory", "New EUC go-live"),
        ])

    if is_legacy and lifecycle in {"Draft", "Submitted", "Registered", "Awaiting Documentation", "Review Ready", "Active"}:
        overlays.extend([
            ("Control Evidence", "Legacy Onboarding", "Legacy onboarding requires current-state control evidence where available; historical evidence is not retrospectively recreated.", True, "Legacy current-state", "Legacy onboarding"),
            ("Reconciliation Evidence", "Legacy Onboarding", "Legacy onboarding requires current or recent reconciliation/control evidence where applicable.", True, "Legacy current-state", "Legacy onboarding"),
            ("Review Evidence", "Legacy Onboarding", "Legacy onboarding may be supported by current review or management attestation.", True, "Legacy current-state", "Legacy onboarding"),
        ])

    open_incidents = get_incidents(euc_id, open_only=True)
    if not open_incidents.empty or lifecycle == "Incident Open":
        overlays.extend([
            ("Incident & RCA Evidence", "Incident Open", "Open incident or near miss requires incident record, containment/correction and RCA evidence.", True, "Event-driven", "Incident"),
            ("Operating Procedure", "Incident Open", "Post-incident hardening may require refreshed operating procedure.", True, "Event-driven", "Incident"),
            ("Library of Controls", "Incident Open", "Post-incident hardening may require refreshed control library.", high_or_very_high, "Event-driven", "Incident"),
            ("Risk Assessment", "Incident Open", "Incident may require reassessment of inherent risk, control effectiveness and residual risk.", True, "Event-driven", "Incident"),
        ])
        if high_or_very_high:
            overlays.extend([
                ("Testing Evidence", "Incident Open", "High/Very High incident-driven correction requires assurance testing where logic, controls or outputs changed.", True, "Event-driven", "Incident-driven correction"),
                ("UAT Evidence", "Incident Open", "High/Very High incident-driven correction may require UAT or independent confirmation that the EUC remains fit for use.", True, "Event-driven", "Incident-driven correction"),
            ])

    open_exceptions = get_exceptions(euc_id, open_only=True)
    if not open_exceptions.empty or lifecycle == "Exception Active":
        overlays.append(("Exception Record", "Exception Active", "Open exception requires documented exception/risk acceptance record.", True, "Event-driven", "Exception"))
        if (euc.get("residual_risk") or "Medium") in {"High", "Very High"}:
            overlays.append(("Approval Evidence", "Exception Active", "High/Very High residual exception requires appropriate approval evidence.", True, "Event-driven", "Exception approval"))

    changes = get_material_changes(euc_id)
    open_changes = changes[~changes["status"].isin(["Closed", "Cancelled", "Withdrawn"])] if not changes.empty and "status" in changes.columns else changes
    if not open_changes.empty or lifecycle in {"Under Change", "Awaiting Reassessment"}:
        overlays.append(("Change & Versioning Evidence", "Under Change", "Material change requires change request/rationale, impact assessment and release/version traceability.", True, "Event-driven", "Material change"))
        if high_or_very_high:
            overlays.extend([
                ("Testing Evidence", "Under Change", "High/Very High inherent material change requires testing evidence.", True, "Event-driven", "Material change"),
                ("UAT Evidence", "Under Change", "High/Very High inherent material change requires UAT or peer test evidence.", True, "Event-driven", "Material change"),
                ("Approval Evidence", "Under Change", "High/Very High inherent material change requires sign-off evidence.", True, "Event-driven", "Material change"),
            ])
        overlays.append(("Risk Assessment", "Under Change", "Material change may require updated risk assessment.", True, "Event-driven", "Material change"))

    residual = euc.get("residual_risk") or "Medium"
    if residual == "High":
        overlays.append(("Review Evidence", lifecycle, "High residual risk requires closer management attention and remediation tracking.", True, "Conditional mandatory", "High residual risk"))
    if residual == "Very High":
        overlays.extend([
            ("Exception Record", lifecycle, "Very High residual risk is outside tolerance; operation requires escalation and/or approved temporary exception.", True, "Conditional mandatory", "Very High residual risk"),
            ("Approval Evidence", lifecycle, "Very High residual risk requires senior approval/escalation evidence if operation continues.", True, "Conditional mandatory", "Very High residual risk"),
        ])

    if lifecycle == "Industrialization Candidate":
        overlays.append(("Industrialization Assessment Evidence", "Industrialization Candidate", "Industrialization candidate requires prioritization/assessment evidence.", True, "Event-driven", "Industrialization"))

    if lifecycle in {"Decommissioned", "Archived"} or (euc.get("overall_status") or "") in {"Decommissioned", "Archived"}:
        overlays.extend([
            ("Decommissioning Evidence", "Decommissioned", "Decommissioning requires final closure evidence.", True, "Event-driven", "Decommissioning"),
            ("Archive Evidence", "Decommissioned", "Decommissioning requires archive/final released version evidence.", True, "Event-driven", "Decommissioning"),
            ("Access Revocation Evidence", "Decommissioned", "Decommissioning requires evidence that legacy access was revoked.", True, "Event-driven", "Decommissioning"),
        ])

    return overlays


def required_documents_for_euc(euc_id: int) -> pd.DataFrame:
    euc = get_euc(euc_id)
    if not euc:
        return pd.DataFrame()

    baseline_info = inherent_baseline_for_euc(euc_id)
    baseline_risk = baseline_info["baseline_risk"]
    reason_prefix = baseline_info["source"]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for doc_type in DEFAULT_REQUIRED_ARTIFACTS.get(baseline_risk, []):
        _append_requirement(rows, seen, baseline_risk, "Active", doc_type, f"{reason_prefix}: {baseline_risk} baseline.", True, "Mandatory baseline", "Inherent risk baseline")

    rules = dataframe(
        """
        SELECT * FROM required_artifact_rules
        WHERE risk_level = ? AND mandatory_flag = 1 AND approval_status = 'Approved'
        ORDER BY required_document_type
        """,
        (baseline_risk,),
    )
    for _, rule in rules.iterrows():
        doc_type = canonical_document_type(rule.get("required_document_type"))
        if not doc_type or doc_type in seen:
            continue
        rows.append(
            {
                "risk_level": baseline_risk,
                "risk_basis": "Overall Inherent Risk",
                "lifecycle_stage": rule.get("lifecycle_stage") or "Active",
                "required_document_type": doc_type,
                "control_area": rule.get("control_area") or _default_rule_metadata(doc_type)[0],
                "cacrt_dimension": rule.get("cacrt_dimension") or _default_rule_metadata(doc_type)[1],
                "mandatory_flag": int(rule.get("mandatory_flag", 1)),
                "requirement_classification": "Mandatory baseline",
                "trigger": "Approved rule",
                "requirement_reason": f"Approved required artifact rule for {baseline_risk} inherent baseline.",
            }
        )
        seen.add(doc_type)

    for doc_type, lifecycle_stage, reason, mandatory, classification, trigger in _event_overlay_requirements(euc, baseline_risk):
        _append_requirement(rows, seen, baseline_risk, lifecycle_stage, doc_type, reason, mandatory, classification, trigger)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["lifecycle_stage", "required_document_type"]).reset_index(drop=True)



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
                status = latest.get("status") or "Submitted"
                document_id = None
                assessment_id = int(latest["assessment_id"])
                reviewed_by = latest.get("reviewed_by") or latest.get("assessed_by")
                comments = (
                    f"Satisfied by risk assessment #{assessment_id}, version {latest.get('version')}. "
                    f"Owner submission status: {status}."
                )
        else:
            assessment_id = None
            if not docs.empty:
                docs_compare = docs.copy()
                docs_compare["_canonical_document_type"] = docs_compare["document_type"].map(lambda v: canonical_document_type(v) or str(v or ""))
                matching = docs_compare[docs_compare["_canonical_document_type"] == doc_type]
            else:
                matching = pd.DataFrame()
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
                "requirement_classification": req.get("requirement_classification", "Mandatory baseline"),
                "trigger": req.get("trigger"),
                "risk_level": req.get("risk_level"),
                "risk_basis": req.get("risk_basis", "Overall Inherent Risk"),
                "lifecycle_stage": req.get("lifecycle_stage"),
                "control_area": req.get("control_area"),
                "cacrt_dimension": req.get("cacrt_dimension"),
                "requirement_reason": req.get("requirement_reason"),
                "what_to_upload": artifact_upload_guidance(doc_type),
                "what_user_should_do": artifact_user_action(doc_type, status),
                "status": status,
                "document_id": document_id,
                "assessment_id": assessment_id,
                "reviewed_by": reviewed_by,
                "comments": comments,
            }
        )
    return pd.DataFrame(rows)


def _lifecycle_for_documentation_status(current_lifecycle: str | None, documentation_status: str) -> str | None:
    """Return an automatic lifecycle transition driven by documentation completeness.

    The artifact checklist is the source of truth for documentation completeness.
    When all mandatory artifacts are accepted or internally satisfied, the EUC
    should leave "Awaiting Documentation" and move to "Review Ready".

    The function intentionally avoids overriding statuses that indicate an
    active governance state such as remediation, incident, exception, change,
    industrialization, decommissioning, or archive.
    """
    current = current_lifecycle or "Registered"
    protected_statuses = {
        "Active",
        "Under Remediation",
        "Exception Active",
        "Incident Open",
        "Under Change",
        "Awaiting Reassessment",
        "Industrialization Candidate",
        "Decommissioned",
        "Archived",
    }
    if current in protected_statuses:
        return None

    pre_review_statuses = {
        "Draft",
        "Submitted",
        "Registered",
        "Risk Assessment In Progress",
        "Awaiting Documentation",
        "Review Ready",
    }
    if documentation_status == "Complete" and current in pre_review_statuses:
        return "Review Ready"
    if documentation_status in {"Incomplete", "Submitted - Pending Review"} and current in pre_review_statuses:
        return "Awaiting Documentation"
    return None


def create_residual_risk_governance_tasks(euc_id: int, username: str) -> int:
    """Create remediation/escalation tasks driven by residual risk.

    Residual risk should not lower the evidence baseline. It drives action: High
    requires remediation planning; Very High is outside tolerance and requires
    escalation/exception governance.
    """
    euc = get_euc(euc_id)
    if not euc:
        return 0
    residual = euc.get("residual_risk") or "Medium"
    created = 0
    if residual not in {"High", "Very High"}:
        return created

    task_specs = []
    if residual == "High":
        task_specs.append(
            {
                "task_type": "Remediation",
                "title": "Create remediation plan for High residual risk",
                "description": "Residual risk is High. Policy requires a remediation plan with target dates and close management attention.",
                "priority": "High",
                "due_days": DEFAULT_DUE_DAYS["Remediation"],
            }
        )
    if residual == "Very High":
        task_specs.append(
            {
                "task_type": "Remediation",
                "title": "Escalate Very High residual risk and raise exception if operation continues",
                "description": "Residual risk is Very High/outside tolerance. Escalation and approved time-bound remediation or temporary exception are required.",
                "priority": "Critical",
                "due_days": 5,
            }
        )

    for spec in task_specs:
        existing = fetch_one(
            """
            SELECT task_id FROM tasks
            WHERE euc_id = ? AND task_type = ? AND title = ? AND status IN ('Open','In Progress','Blocked','Closure Requested')
            LIMIT 1
            """,
            (euc_id, spec["task_type"], spec["title"]),
        )
        if existing:
            continue
        create_task(
            euc_id=euc_id,
            task_type=spec["task_type"],
            title=spec["title"],
            description=spec["description"],
            assigned_to=euc.get("owner"),
            assigned_role=OWNER_ROLE,
            due_date=add_days(spec["due_days"]),
            priority=spec["priority"],
            username=username,
        )
        created += 1
    return created


def evaluate_and_update_completeness(euc_id: int, username: str, create_missing_tasks: bool = False) -> str:
    checklist = artifact_checklist(euc_id)
    if checklist.empty:
        status = "No Rules"
    else:
        mandatory_checklist = checklist[checklist.get("mandatory", True).astype(bool)] if "mandatory" in checklist.columns else checklist
        if mandatory_checklist.empty:
            status = "No Mandatory Rules"
        elif (mandatory_checklist["status"] == "Accepted").all():
            status = "Complete"
        elif mandatory_checklist["status"].isin(["Missing", "Rejected", "Expired"]).any():
            status = "Incomplete"
        else:
            status = "Submitted - Pending Review"

    old_euc = get_euc(euc_id)
    if old_euc:
        new_lifecycle = _lifecycle_for_documentation_status(old_euc.get("lifecycle_status"), status)
        update_payload: dict[str, Any] = {
            "documentation_completeness_status": status,
            "updated_at": utc_now(),
        }
        if new_lifecycle and new_lifecycle != old_euc.get("lifecycle_status"):
            update_payload["lifecycle_status"] = new_lifecycle
            update_payload["overall_status"] = new_lifecycle
            execute(
                """
                UPDATE eucs
                SET documentation_completeness_status = ?, lifecycle_status = ?, overall_status = ?, updated_at = ?
                WHERE euc_id = ?
                """,
                (status, new_lifecycle, new_lifecycle, update_payload["updated_at"], euc_id),
            )
        else:
            execute(
                "UPDATE eucs SET documentation_completeness_status = ?, updated_at = ? WHERE euc_id = ?",
                (status, update_payload["updated_at"], euc_id),
            )
        if (old_euc.get("documentation_completeness_status") != status) or (new_lifecycle and new_lifecycle != old_euc.get("lifecycle_status")):
            insert_audit(
                "EUC",
                euc_id,
                "COMPLETENESS_SYNC",
                username,
                {
                    "documentation_completeness_status": old_euc.get("documentation_completeness_status"),
                    "lifecycle_status": old_euc.get("lifecycle_status"),
                },
                {
                    "documentation_completeness_status": status,
                    "lifecycle_status": new_lifecycle or old_euc.get("lifecycle_status"),
                },
            )
    else:
        execute(
            "UPDATE eucs SET documentation_completeness_status = ?, updated_at = ? WHERE euc_id = ?",
            (status, utc_now(), euc_id),
        )

    if create_missing_tasks:
        create_residual_risk_governance_tasks(euc_id, username)

    if create_missing_tasks and not checklist.empty:
        euc = get_euc(euc_id)
        actionable = checklist[checklist["status"].isin(["Missing", "Rejected", "Expired"])]
        if "mandatory" in actionable.columns:
            actionable = actionable[actionable["mandatory"].astype(bool)]
        for _, row in actionable.iterrows():
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
    queue_task_notification(task_id, username)
    return task_id


def _matches_any_text(row: dict[str, Any], tokens: list[str] | None) -> bool:
    """Return True when no token filter is supplied or any token appears in task text."""
    if not tokens:
        return True
    text = " ".join(str(row.get(field) or "") for field in ("task_type", "title", "description")).lower()
    return any(str(token or "").lower() in text for token in tokens if str(token or "").strip())


def close_task_if_open(
    task_id: int,
    username: str,
    closure_reason: str,
    evidence_document_id: int | None = None,
    action: str = "AUTO_CLOSE",
) -> bool:
    """Close a task once the underlying business action has been completed.

    The task is not deleted. It is closed with a business reason and an audit
    entry, so the control trail remains intact.
    """
    old = fetch_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    if not old or old.get("status") in {"Closed", "Cancelled"}:
        return False

    final_evidence_id = evidence_document_id if evidence_document_id is not None else old.get("closure_evidence_document_id")
    existing_reason = old.get("closure_reason")
    reason = closure_reason if not existing_reason else f"{existing_reason}\n{closure_reason}"
    execute(
        """
        UPDATE tasks
        SET status = 'Closed', closure_reason = ?, closure_evidence_document_id = ?, closed_at = ?
        WHERE task_id = ?
        """,
        (reason, final_evidence_id, utc_now(), task_id),
    )
    insert_audit("Task", task_id, action, username, old, {"status": "Closed", "closure_reason": closure_reason, "closure_evidence_document_id": final_evidence_id})
    queue_direct_notification(
        event_type="TASK_AUTO_CLOSED",
        entity_type="Task",
        entity_id=task_id,
        euc_id=old.get("euc_id"),
        triggered_by=username,
        subject=f"[EUC Governance] Task auto-closed: {old.get('title')}",
        body=f"The task was automatically closed because the underlying action was completed. Reason: {closure_reason}",
        recipient_username=old.get("assigned_to"),
        recipient_role=old.get("assigned_role") if not old.get("assigned_to") else None,
    )
    return True


def auto_close_tasks(
    euc_id: int | None,
    username: str,
    task_types: list[str],
    closure_reason: str,
    title_or_description_tokens: list[str] | None = None,
    evidence_document_id: int | None = None,
) -> int:
    """Close open tasks for an EUC when the user completes the related action."""
    if not euc_id or not task_types:
        return 0
    placeholders = ",".join("?" for _ in task_types)
    rows = fetch_all(
        f"""
        SELECT * FROM tasks
        WHERE euc_id = ?
          AND task_type IN ({placeholders})
          AND status IN ('Open','In Progress','Blocked','Closure Requested')
        """,
        tuple([euc_id, *task_types]),
    )
    closed = 0
    for row in rows:
        if _matches_any_text(row, title_or_description_tokens):
            if close_task_if_open(int(row["task_id"]), username, closure_reason, evidence_document_id=evidence_document_id):
                closed += 1
    return closed


def auto_close_tasks_for_risk_assessment(euc_id: int, assessment_id: int, username: str) -> int:
    """Close risk-assessment tasks once an assessment version is submitted."""
    reason = f"Auto-closed because risk assessment #{assessment_id} was completed for this EUC."
    closed = auto_close_tasks(
        euc_id=euc_id,
        username=username,
        task_types=["Risk assessment", "Reassessment"],
        closure_reason=reason,
        title_or_description_tokens=["risk assessment", "reassess", "reassessment"],
    )
    closed += auto_close_tasks(
        euc_id=euc_id,
        username=username,
        task_types=["Missing evidence"],
        closure_reason=reason,
        title_or_description_tokens=["risk assessment"],
    )
    return closed


def auto_close_tasks_for_document_submission(euc_id: int, document_id: int, document_type: str, username: str) -> int:
    """Close evidence-submission tasks once the requested evidence is uploaded."""
    doc_type = document_type or "document"
    reason = f"Auto-closed because {doc_type} evidence was uploaded as document #{document_id}."
    closed = auto_close_tasks(
        euc_id=euc_id,
        username=username,
        task_types=["Document submission"],
        closure_reason=reason,
        evidence_document_id=document_id,
    )
    closed += auto_close_tasks(
        euc_id=euc_id,
        username=username,
        task_types=["Missing evidence", "Closure evidence"],
        closure_reason=reason,
        title_or_description_tokens=[doc_type, "evidence"],
        evidence_document_id=document_id,
    )
    if doc_type in {"Operating Procedure", "Library of Controls", "Review Evidence", "Testing Evidence", "Reconciliation Evidence", "Resilience Evidence"}:
        closed += auto_close_tasks(
            euc_id=euc_id,
            username=username,
            task_types=["Documentation refresh"],
            closure_reason=reason,
            title_or_description_tokens=["documentation", "refresh", doc_type],
            evidence_document_id=document_id,
        )
    return closed


def auto_close_tasks_for_exception_decision(euc_id: int | None, exception_id: int, username: str, approval_status: str) -> int:
    return auto_close_tasks(
        euc_id=euc_id,
        username=username,
        task_types=["Review response"],
        closure_reason=f"Auto-closed because exception #{exception_id} was {approval_status.lower()}.",
        title_or_description_tokens=[f"exception {exception_id}", "approve or reject exception"],
    )


def auto_close_tasks_for_finding_closure(euc_id: int | None, finding_id: int, username: str) -> int:
    return auto_close_tasks(
        euc_id=euc_id,
        username=username,
        task_types=["Remediation"],
        closure_reason=f"Auto-closed because finding #{finding_id} was closed.",
        title_or_description_tokens=[f"finding {finding_id}", "remediate finding"],
    )


def get_tasks(role: str | None = None, username: str | None = None, open_only: bool = False) -> pd.DataFrame:
    """Return tasks with the correct UI scope.

    When called without a role/username, this function intentionally returns the
    portfolio task set for governance monitoring/reporting pages. When called
    from the Tasks & Remediation page with the logged-in context, it returns only
    records that are relevant to that user:

    * direct assignments to the username;
    * role-queue assignments for central workflow roles;
    * tasks on EUCs owned/delegated/created by the user;
    * for EUC Owner/Contributor role queues, only role tasks linked to that
      user's own/delegated/created EUCs, so one owner does not see every task
      assigned to the generic "EUC Owner" role.
    """
    where = []
    params: list[Any] = []
    if open_only:
        where.append("t.status IN ('Open','In Progress','Blocked','Closure Requested')")

    if role and username:
        personal_euc_sql = "(e.owner = ? OR e.owner_delegate = ? OR e.created_by = ?)"
        if role in {GCC_ROLE, DVU_ROLE, ADMIN_ROLE, APPROVER_ROLE}:
            # Central roles see tasks assigned directly to them or to their
            # role queue, not every task in the database. Portfolio-wide task
            # views call get_tasks without a user context.
            where.append("(t.assigned_to = ? OR t.assigned_role = ?)")
            params.extend([username, role])
        else:
            where.append(
                "("
                "t.assigned_to = ? "
                "OR " + personal_euc_sql + " "
                "OR (t.assigned_role = ? AND " + personal_euc_sql + ")"
                ")"
            )
            params.extend([username, username, username, username, role, username, username, username])

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
    queue_direct_notification(
        event_type="TASK_UPDATED",
        entity_type="Task",
        entity_id=task_id,
        euc_id=old.get("euc_id"),
        triggered_by=username,
        subject=f"[EUC Governance] Task updated: {old.get('title')}",
        body=f"Task status changed to {status}. Closure reason: {closure_reason or '-'}",
        recipient_username=old.get("assigned_to"),
        recipient_role=old.get("assigned_role") if not old.get("assigned_to") else None,
    )


def update_task_admin_fields(task_id: int, due_date: str | None, priority: str | None, username: str) -> None:
    """Update non-closure task fields from the selected task edit form."""
    old = fetch_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    if not old:
        raise ValueError("Task not found")
    execute(
        """
        UPDATE tasks
        SET due_date = ?, priority = ?
        WHERE task_id = ?
        """,
        (due_date, priority, task_id),
    )
    insert_audit("Task", task_id, "UPDATE", username, old, {"due_date": due_date, "priority": priority})


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
    queue_raci_notifications(
        "INDEPENDENT_REVIEW_COMPLETED",
        "Review",
        review_id,
        payload["euc_id"],
        username,
        context={"Review type": payload.get("review_type", "Data Validation"), "Outcome": payload.get("outcome")},
    )
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
    queue_raci_notifications(
        "FINDING_RAISED",
        "Finding",
        finding_id,
        payload["euc_id"],
        username,
        context={"Severity": payload.get("severity"), "Requirement": payload.get("requirement"), "Assigned to": payload.get("assigned_to")},
    )
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
    if status == "Closed":
        auto_close_tasks_for_finding_closure(old.get("euc_id"), finding_id, username)


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
    fields = [
        "euc_id", "control_gap", "root_cause", "compensating_controls", "residual_risk", "remediation_plan",
        "target_date", "expiry_date", "approval_status", "approved_by", "status", "exception_owner",
        "milestones", "monitoring_approach", "periodic_review_date", "renewal_status", "renewal_request_reason",
        "renewal_evidence_document_id", "escalation_required", "escalation_to", "escalation_date",
        "senior_management_approval", "bcbs239_steering_reported", "unit_head_approval", "closure_evidence_document_id",
        "created_at",
    ]
    values = {
        **payload,
        "approval_status": payload.get("approval_status", "Pending"),
        "status": payload.get("status", "Open"),
        "exception_owner": payload.get("exception_owner") or payload.get("assigned_to") or username,
        "created_at": utc_now(),
    }
    exception_id = execute(
        f"INSERT INTO exceptions({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(values.get(field) for field in fields),
    )
    insert_audit("Exception", exception_id, "CREATE", username, None, payload)
    queue_raci_notifications(
        "EXCEPTION_RAISED",
        "Exception",
        exception_id,
        payload["euc_id"],
        username,
        context={
            "Control gap": payload.get("control_gap"),
            "Residual risk": payload.get("residual_risk"),
            "Approval status": payload.get("approval_status", "Pending"),
            "Escalation required": payload.get("escalation_required"),
        },
    )
    update_euc_status(payload["euc_id"], "Exception Active", username, "Exception active")
    create_task(
        euc_id=payload["euc_id"],
        task_type="Review response",
        title=f"Approve or reject exception {exception_id}",
        description=payload["control_gap"],
        assigned_to=None,
        assigned_role=APPROVER_ROLE,
        due_date=add_days(7),
        priority="Critical" if payload.get("residual_risk") == "Very High" else "High",
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
    queue_raci_notifications(
        "EXCEPTION_DECISION",
        "Exception",
        exception_id,
        old.get("euc_id"),
        approved_by,
        context={"Approval status": approval_status, "Approved by": approved_by},
    )
    auto_close_tasks_for_exception_decision(old.get("euc_id"), exception_id, approved_by, approval_status)


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
    fields = [
        "euc_id", "affected_outputs", "incident_date", "detection_date", "reporting_period_run", "reported_by",
        "incident_type", "incident_description", "impact_summary", "impact_description", "severity", "cacrt_dimension",
        "root_cause_category", "root_cause_description", "containment_status", "correction_status", "rca_status",
        "immediate_action_taken", "corrective_action", "preventive_action", "remediation_actions", "action_owner",
        "target_resolution_date", "resolution_date", "linked_residual_risk_level", "regulatory_impact", "escalated",
        "escalation_date", "escalation_to", "restatement_reissue_required", "exception_raised", "reference_links_evidence",
        "comments", "status", "created_at",
    ]
    values = {
        **payload,
        "incident_date": payload.get("incident_date", date.today().isoformat()),
        "reported_by": payload.get("reported_by") or username,
        "status": payload.get("status", "Open"),
        "created_at": utc_now(),
    }
    incident_id = execute(
        f"INSERT INTO incidents({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(values.get(field) for field in fields),
    )
    insert_audit("Incident", incident_id, "CREATE", username, None, payload)
    queue_raci_notifications(
        "INCIDENT_LOGGED",
        "Incident",
        incident_id,
        payload["euc_id"],
        username,
        context={
            "Incident date": values.get("incident_date"),
            "Affected outputs": payload.get("affected_outputs"),
            "Severity": payload.get("severity"),
            "Status": values.get("status"),
        },
    )
    euc = get_euc(payload["euc_id"])
    execute(
        "UPDATE eucs SET incident_near_miss_count = COALESCE(incident_near_miss_count, 0) + 1, last_incident_date = ?, updated_at = ? WHERE euc_id = ?",
        (values.get("incident_date"), utc_now(), payload["euc_id"]),
    )
    update_euc_status(payload["euc_id"], "Incident Open", username, "Incident open")
    create_task(payload["euc_id"], "Reassessment", f"Reassess EUC after incident {incident_id}", payload.get("impact_summary") or payload.get("impact_description"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Reassessment"]), "High", username)
    create_task(payload["euc_id"], "Documentation refresh", f"Refresh documentation after incident {incident_id}", payload.get("remediation_actions") or payload.get("corrective_action"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Documentation refresh"]), "High", username)
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
    fields = [
        "euc_id", "change_type", "description", "change_request_rationale", "impact_assessment", "cutover_plan",
        "rollback_approach", "change_stage", "testing_required", "uat_required", "approval_required", "approval_status",
        "approved_by", "approval_date", "reassessment_required", "documentation_refresh_required",
        "library_controls_update_required", "evidence_pack_update_detail", "stakeholder_communication",
        "communication_date", "effective_date", "emergency_change", "retro_uat_required", "status", "created_by", "created_at",
    ]
    values = {
        **payload,
        "testing_required": int(bool(payload.get("testing_required"))),
        "uat_required": int(bool(payload.get("uat_required"))),
        "approval_required": int(bool(payload.get("approval_required"))),
        "reassessment_required": int(bool(payload.get("reassessment_required"))),
        "documentation_refresh_required": int(bool(payload.get("documentation_refresh_required"))),
        "library_controls_update_required": int(bool(payload.get("library_controls_update_required"))),
        "emergency_change": int(bool(payload.get("emergency_change"))),
        "retro_uat_required": int(bool(payload.get("retro_uat_required"))),
        "status": payload.get("status", "Open"),
        "created_by": username,
        "created_at": utc_now(),
    }
    change_id = execute(
        f"INSERT INTO material_changes({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(values.get(field) for field in fields),
    )
    insert_audit("Material Change", change_id, "CREATE", username, None, payload)
    queue_raci_notifications(
        "MATERIAL_CHANGE_LOGGED",
        "Material Change",
        change_id,
        payload["euc_id"],
        username,
        context={"Change type": payload.get("change_type"), "Reassessment required": payload.get("reassessment_required"), "Documentation refresh required": payload.get("documentation_refresh_required")},
    )
    euc = get_euc(payload["euc_id"])
    update_euc_status(payload["euc_id"], "Under Change", username, "Under change")
    if payload.get("reassessment_required"):
        create_task(payload["euc_id"], "Reassessment", f"Reassess EUC after material change {change_id}", payload.get("impact_assessment"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Reassessment"]), "High", username)
    if payload.get("documentation_refresh_required"):
        create_task(payload["euc_id"], "Documentation refresh", f"Refresh documentation after material change {change_id}", payload.get("description"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Documentation refresh"]), "Medium", username)
    if payload.get("library_controls_update_required"):
        create_task(payload["euc_id"], "Documentation refresh", f"Refresh Library of Controls after material change {change_id}", payload.get("description"), euc.get("owner") if euc else None, OWNER_ROLE, add_days(DEFAULT_DUE_DAYS["Documentation refresh"]), "Medium", username)
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



def inventory_completeness_migration_dataset() -> pd.DataFrame:
    """Portfolio view of post-registration inventory completeness and migration fields."""
    return dataframe(
        """
        SELECT
            e.euc_id, e.reference_id, e.name, e.owner, e.business_unit, e.lifecycle_status,
            e.inherent_risk, e.residual_risk, e.documentation_completeness_status,
            e.registration_date, e.go_live_date, e.evidence_pack_location, e.library_controls_link,
            e.risk_assessment_link, e.documentation_gap_assessment_required, e.documentation_gaps_summary,
            e.material_mapping_confidence, e.migration_status, e.migration_notes,
            e.legacy_sensitive_data_flag, e.legacy_criticality,
            COUNT(DISTINCT CASE WHEN g.status NOT IN ('Closed','Cancelled','Accepted Risk') THEN g.gap_id END) AS open_documentation_gaps,
            COUNT(DISTINCT CASE WHEN d.status = 'Accepted' THEN d.document_id END) AS accepted_evidence_count,
            COUNT(DISTINCT c.component_id) AS asset_count
        FROM eucs e
        LEFT JOIN documentation_gaps g ON g.euc_id = e.euc_id
        LEFT JOIN documents d ON d.euc_id = e.euc_id
        LEFT JOIN components c ON c.euc_id = e.euc_id
        GROUP BY e.euc_id
        ORDER BY e.business_unit, e.reference_id
        """
    )

def asset_migration_dataset() -> pd.DataFrame:
    """Asset-level migration and legacy conversion monitoring view for GCC/Admin."""
    return dataframe(
        """
        SELECT
            c.component_id, c.euc_id, e.reference_id, e.name AS euc_application, e.business_unit,
            c.component_name, c.technology_type, c.controlled_storage_location, c.owner AS asset_steward,
            c.criticality, c.material_mapping_confidence, c.asset_migration_status, c.asset_migration_notes,
            c.legacy_sensitive_data_flag, c.legacy_criticality, c.legacy_support_contract_sla,
            c.cots_third_party_component, c.vendor_tool_name, c.vendor_support_status, c.end_of_support_date
        FROM components c
        JOIN eucs e ON e.euc_id = c.euc_id
        ORDER BY e.business_unit, e.reference_id, c.component_name
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
        "documentation_gaps": get_documentation_gaps(open_only=True),
        "high_criticality_reviews": get_high_criticality_reviews(),
        "industrialization_assessments": get_industrialization_assessments(),
        "inventory_completeness_migration": inventory_completeness_migration_dataset(),
        "asset_migration": asset_migration_dataset(),
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



# ---------------------------------------------------------------------------
# Policy MI, KPI and custom reporting
# ---------------------------------------------------------------------------

POLICY_REPORTS = [
    {
        "key": "inventory_risk_profile",
        "name": "Inventory coverage & risk profile distribution",
        "policy_basis": "Policy 2.2.7 requires inventory coverage, overall inherent/residual risk distribution, overdue reviews, exception ageing, incidents, remediation and industrialization pipeline, and area segments.",
        "description": "Portfolio view by business unit, lifecycle, inherent risk, residual risk and documentation completeness.",
    },
    {
        "key": "bcbs_output_coverage",
        "name": "EUC ↔ BCBS 239 output coverage",
        "policy_basis": "Policy 2.2.7 requires coverage of linkages to BCBS 239 in-scope outputs and completeness of operationalization documentation.",
        "description": "Shows EUCs mapped to BCBS 239 outputs and whether operating/operationalization documentation is accepted.",
    },
    {
        "key": "inventory_quality",
        "name": "Inventory completeness & quality report",
        "policy_basis": "Policy 2.2.2 requires an annual completeness and quality report covering missing mappings, overdue reviews and High/Very High inherent-risk coverage.",
        "description": "Flags missing mappings, overdue reviews, incomplete evidence packs and High/Very High inherent EUCs without accepted key evidence.",
    },
    {
        "key": "library_kpis",
        "name": "Library of Controls KPI",
        "policy_basis": "Policy 2.2.7 requires % EUCs with Library of Controls.",
        "description": "Shows accepted Library of Controls coverage by business unit and risk band.",
    },
    {
        "key": "cacrt_coverage",
        "name": "CACRT coverage per EUC and dimension",
        "policy_basis": "Policy 2.2.7 requires % CACRT coverage per EUC and per CACRT dimension.",
        "description": "Rule-based coverage of accepted/satisfied artifacts mapped to CACRT dimensions.",
    },
    {
        "key": "incident_resolution",
        "name": "Incidents and resolution time",
        "policy_basis": "Policy 2.2.7 requires incidents and resolution-time KPIs.",
        "description": "Incident log with ageing/resolution indicators and affected outputs.",
    },
    {
        "key": "exception_ageing",
        "name": "Exception ageing and expiry",
        "policy_basis": "Policy 2.2.7 requires exception ageing as part of MI and governance reporting.",
        "description": "Open/approved/rejected exceptions with age, days to expiry and residual-risk context.",
    },
    {
        "key": "remediation_pipeline",
        "name": "Remediation and findings pipeline",
        "policy_basis": "Policy 2.2.7 requires remediation pipeline reporting; RACI assigns Data Validation findings and GCC governance reporting accountability.",
        "description": "Open tasks and findings by owner, severity, due date and ageing.",
    },
    {
        "key": "industrialization_pipeline",
        "name": "Industrialization and decommissioning pipeline",
        "policy_basis": "Policy 2.2.7 and lifecycle rules require industrialization pipeline and decommissioning status visibility.",
        "description": "Industrialization candidates, decommissioned/archived EUCs and scoring signals.",
    },
    {
        "key": "high_criticality_review_coverage",
        "name": "High-criticality Evidence Pack / Independent Review coverage",
        "policy_basis": "Policy 2.2.6 requires High-Criticality Evidence Pack and Independent Review checklist for material BCBS 239 High/Very High inherent EUCs.",
        "description": "Shows material BCBS 239 High/Very High inherent EUCs and latest high-criticality review outcome.",
    },
    {
        "key": "documentation_gap_pipeline",
        "name": "Legacy onboarding documentation gaps and dispositions",
        "policy_basis": "Legacy onboarding requires identification of documentation, control and evidence gaps, with remediation actions, exceptions or risk acceptance where gaps cannot be closed immediately.",
        "description": "Shows open and closed documentation gaps, disposition, severity, owner and target date.",
    },
    {
        "key": "lineage_completeness",
        "name": "High / Very High inherent EUCs with complete lineage",
        "policy_basis": "Policy 2.2.7 requires % High/Very High inherent EUCs with complete lineage.",
        "description": "Flags High/Very High inherent EUCs with documented inputs, outputs, dependencies, CDE linkages and asset-level lineage data.",
    },
    {
        "key": "overdue_reviews",
        "name": "Overdue reviews",
        "policy_basis": "Policy 2.2.2 and 2.2.7 require reporting of overdue reviews.",
        "description": "EUCs with next review date before today.",
    },
]

CUSTOM_REPORT_DATASETS = {
    "EUC Portfolio": "euc_portfolio",
    "Tasks": "tasks",
    "Documents / Evidence": "documents",
    "Risk Assessments": "risk_assessments",
    "Findings": "findings",
    "Exceptions": "exceptions",
    "Incidents": "incidents",
    "Material Changes": "material_changes",
    "Components / Assets": "components",
    "Documentation Gaps": "documentation_gaps",
    "High-Criticality Reviews": "high_criticality_reviews",
    "Industrialization Assessments": "industrialization_assessments",
}


def policy_report_catalog() -> list[dict[str, str]]:
    return POLICY_REPORTS.copy()


def custom_report_dataset_names() -> list[str]:
    return list(CUSTOM_REPORT_DATASETS.keys())


def _report_euc_where(filters: dict[str, Any] | None, alias: str = "e") -> tuple[str, list[Any]]:
    filters = filters or {}
    where = []
    params: list[Any] = []
    a = alias
    if filters.get("owner") and filters["owner"] != "All":
        where.append(f"{a}.owner = ?")
        params.append(filters["owner"])
    if filters.get("business_unit") and filters["business_unit"] != "All":
        where.append(f"{a}.business_unit = ?")
        params.append(filters["business_unit"])
    if filters.get("inherent_risk") and filters["inherent_risk"] != "All":
        where.append(f"e.inherent_risk = ?")
        params.append(filters["inherent_risk"])
    if filters.get("residual_risk") and filters["residual_risk"] != "All":
        where.append(f"{a}.residual_risk = ?")
        params.append(filters["residual_risk"])
    if filters.get("lifecycle_status") and filters["lifecycle_status"] != "All":
        where.append(f"{a}.lifecycle_status = ?")
        params.append(filters["lifecycle_status"])
    if filters.get("output_mapping"):
        where.append(f"lower({a}.bcbs239_output_mapping) LIKE lower(?)")
        params.append(f"%{filters['output_mapping']}%")
    return (" AND ".join(where) if where else "1=1", params)


def policy_kpi_cards(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    where, params = _report_euc_where(filters, "e")
    row = fetch_one(
        f"""
        SELECT
            COUNT(*) AS total_eucs,
            SUM(CASE WHEN COALESCE(NULLIF(TRIM(e.bcbs239_output_mapping), ''), '') <> '' THEN 1 ELSE 0 END) AS mapped_eucs,
            SUM(CASE WHEN e.documentation_completeness_status = 'Complete' THEN 1 ELSE 0 END) AS docs_complete,
            SUM(CASE WHEN e.inherent_risk IN ('High','Very High') THEN 1 ELSE 0 END) AS high_vh_inherent,
            SUM(CASE WHEN e.residual_risk IN ('High','Very High') THEN 1 ELSE 0 END) AS high_vh_residual,
            SUM(CASE WHEN e.next_review_date IS NOT NULL AND date(e.next_review_date) < date('now') THEN 1 ELSE 0 END) AS overdue_reviews,
            SUM(CASE WHEN e.lifecycle_status = 'Industrialization Candidate' THEN 1 ELSE 0 END) AS industrialization_candidates,
            SUM(CASE WHEN e.lifecycle_status IN ('Decommissioned','Archived') THEN 1 ELSE 0 END) AS decommissioned_archived
        FROM eucs e
        WHERE {where}
        """,
        tuple(params),
    ) or {}
    incident_row = fetch_one(
        f"""
        SELECT COUNT(DISTINCT i.incident_id) AS open_incidents
        FROM incidents i JOIN eucs e ON e.euc_id = i.euc_id
        WHERE {where} AND COALESCE(i.status, 'Open') NOT IN ('Closed','Cancelled')
        """,
        tuple(params),
    ) or {}
    exception_row = fetch_one(
        f"""
        SELECT COUNT(DISTINCT ex.exception_id) AS open_exceptions
        FROM exceptions ex JOIN eucs e ON e.euc_id = ex.euc_id
        WHERE {where} AND COALESCE(ex.status, 'Open') NOT IN ('Closed','Cancelled','Withdrawn')
        """,
        tuple(params),
    ) or {}
    remediation_row = fetch_one(
        f"""
        SELECT COUNT(DISTINCT t.task_id) AS open_remediation
        FROM tasks t LEFT JOIN eucs e ON e.euc_id = t.euc_id
        WHERE {where} AND t.status NOT IN ('Closed','Cancelled')
          AND t.task_type IN ('Remediation','Missing evidence','Review response','Closure evidence','Reassessment','Documentation refresh')
        """,
        tuple(params),
    ) or {}
    library_row = fetch_one(
        f"""
        SELECT COUNT(DISTINCT e.euc_id) AS total_eucs,
               COUNT(DISTINCT CASE WHEN d.status = 'Accepted' THEN e.euc_id END) AS with_library
        FROM eucs e
        LEFT JOIN documents d ON d.euc_id = e.euc_id AND d.document_type = 'Library of Controls'
        WHERE {where}
        """,
        tuple(params),
    ) or {}
    op_row = fetch_one(
        f"""
        SELECT COUNT(DISTINCT CASE WHEN COALESCE(NULLIF(TRIM(e.bcbs239_output_mapping), ''), '') <> '' THEN e.euc_id END) AS mapped_eucs,
               COUNT(DISTINCT CASE WHEN COALESCE(NULLIF(TRIM(e.bcbs239_output_mapping), ''), '') <> '' AND d.status = 'Accepted' THEN e.euc_id END) AS with_operationalization_doc
        FROM eucs e
        LEFT JOIN documents d ON d.euc_id = e.euc_id AND d.document_type = 'Operating Procedure'
        WHERE {where}
        """,
        tuple(params),
    ) or {}
    total = int(row.get("total_eucs") or 0)
    with_library = int(library_row.get("with_library") or 0)
    mapped = int(op_row.get("mapped_eucs") or 0)
    with_op = int(op_row.get("with_operationalization_doc") or 0)
    return {
        "Total EUCs": total,
        "BCBS-mapped EUCs": int(row.get("mapped_eucs") or 0),
        "Docs complete": int(row.get("docs_complete") or 0),
        "High / Very High inherent": int(row.get("high_vh_inherent") or 0),
        "High / Very High residual": int(row.get("high_vh_residual") or 0),
        "Overdue reviews": int(row.get("overdue_reviews") or 0),
        "Open incidents": int(incident_row.get("open_incidents") or 0),
        "Open exceptions": int(exception_row.get("open_exceptions") or 0),
        "Open remediation items": int(remediation_row.get("open_remediation") or 0),
        "Industrialization candidates": int(row.get("industrialization_candidates") or 0),
        "Library of Controls coverage %": round((with_library / total * 100), 1) if total else 0.0,
        "Operationalization documentation %": round((with_op / mapped * 100), 1) if mapped else 0.0,
        "Open documentation gaps": _count("SELECT COUNT(*) AS n FROM documentation_gaps WHERE status NOT IN ('Closed','Cancelled','Accepted Risk')"),
        "High-criticality reviews": _count("SELECT COUNT(*) AS n FROM high_criticality_reviews"),
    }


def policy_report_charts(filters: dict[str, Any] | None = None) -> dict[str, pd.DataFrame]:
    where, params = _report_euc_where(filters, "e")
    return {
        "inherent_risk": dataframe(f"SELECT e.inherent_risk AS risk_level, COUNT(*) AS count FROM eucs e WHERE {where} GROUP BY e.inherent_risk", tuple(params)),
        "residual_risk": dataframe(f"SELECT e.residual_risk AS risk_level, COUNT(*) AS count FROM eucs e WHERE {where} GROUP BY e.residual_risk", tuple(params)),
        "lifecycle": dataframe(f"SELECT e.lifecycle_status, COUNT(*) AS count FROM eucs e WHERE {where} GROUP BY e.lifecycle_status ORDER BY count DESC", tuple(params)),
        "business_unit": dataframe(f"SELECT e.business_unit, COUNT(*) AS count FROM eucs e WHERE {where} GROUP BY e.business_unit ORDER BY count DESC", tuple(params)),
    }


def _accepted_doc_exists_sql(doc_type: str) -> str:
    canonical = canonical_document_type(doc_type) or doc_type
    aliases = [canonical] + [old for old, new in LEGACY_DOCUMENT_TYPE_ALIASES.items() if new == canonical]
    values = ", ".join("'" + str(v).replace("'", "''") + "'" for v in aliases if v)
    return f"EXISTS (SELECT 1 FROM documents d WHERE d.euc_id = e.euc_id AND d.document_type IN ({values}) AND d.status = 'Accepted')"


def run_policy_report(report_key: str, filters: dict[str, Any] | None = None) -> pd.DataFrame:
    where, params = _report_euc_where(filters, "e")
    if report_key == "inventory_risk_profile":
        return dataframe(
            f"""
            SELECT e.business_unit, e.lifecycle_status, e.inherent_risk, e.residual_risk,
                   e.documentation_completeness_status,
                   COUNT(*) AS euc_count,
                   SUM(CASE WHEN e.spof_indicator = 'Yes' THEN 1 ELSE 0 END) AS spof_count,
                   SUM(CASE WHEN e.next_review_date IS NOT NULL AND date(e.next_review_date) < date('now') THEN 1 ELSE 0 END) AS overdue_reviews
            FROM eucs e
            WHERE {where}
            GROUP BY e.business_unit, e.lifecycle_status, e.inherent_risk, e.residual_risk, e.documentation_completeness_status
            ORDER BY e.business_unit, e.inherent_risk DESC, e.residual_risk DESC
            """,
            tuple(params),
        )
    if report_key == "bcbs_output_coverage":
        return dataframe(
            f"""
            SELECT e.reference_id, e.name, e.owner, e.business_unit,
                   e.bcbs239_output_mapping,
                   CASE WHEN COALESCE(NULLIF(TRIM(e.bcbs239_output_mapping), ''), '') = '' THEN 'Missing mapping' ELSE 'Mapped' END AS mapping_status,
                   CASE WHEN {_accepted_doc_exists_sql('Operating Procedure')} THEN 'Accepted' ELSE 'Missing / not accepted' END AS operating_procedure_status,
                   CASE WHEN {_accepted_doc_exists_sql('Library of Controls')} THEN 'Accepted' ELSE 'Missing / not accepted' END AS library_of_controls_status,
                   CASE WHEN {_accepted_doc_exists_sql('Review Evidence')} THEN 'Accepted' ELSE 'Missing / not accepted' END AS review_evidence_status,
                   e.documentation_completeness_status, e.lifecycle_status, e.inherent_risk, e.residual_risk
            FROM eucs e
            WHERE {where}
            ORDER BY mapping_status DESC, e.business_unit, e.reference_id
            """,
            tuple(params),
        )
    if report_key == "inventory_quality":
        return dataframe(
            f"""
            SELECT e.reference_id, e.name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk, e.lifecycle_status,
                   e.documentation_completeness_status, e.next_review_date,
                   CASE WHEN COALESCE(NULLIF(TRIM(e.bcbs239_output_mapping), ''), '') = '' THEN 1 ELSE 0 END AS missing_bcbs_mapping,
                   CASE WHEN e.next_review_date IS NOT NULL AND date(e.next_review_date) < date('now') THEN 1 ELSE 0 END AS overdue_review,
                   CASE WHEN e.inherent_risk IN ('High','Very High') THEN 1 ELSE 0 END AS high_vh_inherent,
                   CASE WHEN e.inherent_risk IN ('High','Very High') AND {_accepted_doc_exists_sql('Library of Controls')} THEN 1 ELSE 0 END AS high_vh_library_accepted,
                   CASE WHEN e.inherent_risk IN ('High','Very High') AND {_accepted_doc_exists_sql('Reconciliation Evidence')} THEN 1 ELSE 0 END AS high_vh_reconciliation_accepted,
                   CASE WHEN e.inherent_risk IN ('High','Very High') AND {_accepted_doc_exists_sql('Resilience Evidence')} THEN 1 ELSE 0 END AS high_vh_resilience_accepted
            FROM eucs e
            WHERE {where}
            ORDER BY missing_bcbs_mapping DESC, overdue_review DESC, e.inherent_risk DESC, e.reference_id
            """,
            tuple(params),
        )
    if report_key == "library_kpis":
        return dataframe(
            f"""
            SELECT e.business_unit, e.inherent_risk,
                   COUNT(DISTINCT e.euc_id) AS total_eucs,
                   COUNT(DISTINCT CASE WHEN d.status = 'Accepted' THEN e.euc_id END) AS eucs_with_accepted_library,
                   ROUND(100.0 * COUNT(DISTINCT CASE WHEN d.status = 'Accepted' THEN e.euc_id END) / NULLIF(COUNT(DISTINCT e.euc_id), 0), 1) AS library_coverage_pct
            FROM eucs e
            LEFT JOIN documents d ON d.euc_id = e.euc_id AND d.document_type = 'Library of Controls'
            WHERE {where}
            GROUP BY e.business_unit, e.inherent_risk
            ORDER BY e.business_unit, e.inherent_risk DESC
            """,
            tuple(params),
        )
    if report_key == "cacrt_coverage":
        eucs = dataframe(f"SELECT e.euc_id, e.reference_id, e.name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk FROM eucs e WHERE {where} ORDER BY e.reference_id", tuple(params))
        rows: list[dict[str, Any]] = []
        for _, euc in eucs.iterrows():
            checklist = artifact_checklist(int(euc["euc_id"]))
            if checklist.empty:
                rows.append({**euc.to_dict(), "cacrt_dimension": "No rule", "required_artifacts": 0, "accepted_or_satisfied": 0, "coverage_pct": 0.0})
                continue
            checklist = checklist.copy()
            checklist["cacrt_dimension"] = checklist["cacrt_dimension"].fillna("Unmapped")
            for dim, group in checklist.groupby("cacrt_dimension"):
                required = len(group)
                accepted = int(group["status"].isin(["Accepted"]).sum())
                rows.append({**euc.to_dict(), "cacrt_dimension": dim, "required_artifacts": required, "accepted_or_satisfied": accepted, "coverage_pct": round(accepted / required * 100, 1) if required else 0.0})
        return pd.DataFrame(rows)
    if report_key == "incident_resolution":
        return dataframe(
            f"""
            SELECT i.incident_id, e.reference_id, e.name, e.owner, e.business_unit, e.residual_risk,
                   i.affected_outputs, i.incident_date, i.impact_summary,
                   i.containment_status, i.correction_status, i.rca_status, COALESCE(i.status, 'Open') AS status,
                   CAST(julianday(CASE WHEN COALESCE(i.status, 'Open') = 'Closed' THEN i.created_at ELSE date('now') END) - julianday(i.incident_date) AS INTEGER) AS days_since_incident
            FROM incidents i JOIN eucs e ON e.euc_id = i.euc_id
            WHERE {where}
            ORDER BY status, days_since_incident DESC
            """,
            tuple(params),
        )
    if report_key == "exception_ageing":
        return dataframe(
            f"""
            SELECT ex.exception_id, e.reference_id, e.name, e.owner, e.business_unit,
                   ex.control_gap, ex.residual_risk, ex.approval_status, COALESCE(ex.status, 'Open') AS status,
                   ex.target_date, ex.expiry_date,
                   CAST(julianday(date('now')) - julianday(ex.created_at) AS INTEGER) AS age_days,
                   CASE WHEN ex.expiry_date IS NOT NULL THEN CAST(julianday(ex.expiry_date) - julianday(date('now')) AS INTEGER) END AS days_to_expiry
            FROM exceptions ex JOIN eucs e ON e.euc_id = ex.euc_id
            WHERE {where}
            ORDER BY status, days_to_expiry, age_days DESC
            """,
            tuple(params),
        )
    if report_key == "remediation_pipeline":
        tasks = dataframe(
            f"""
            SELECT 'Task' AS item_type, t.task_id AS item_id, e.reference_id, e.name, e.owner, e.business_unit,
                   t.task_type AS category, t.title AS summary, t.assigned_to, t.assigned_role, t.priority, t.status, t.due_date,
                   CASE WHEN t.due_date IS NOT NULL AND date(t.due_date) < date('now') AND t.status NOT IN ('Closed','Cancelled') THEN 1 ELSE 0 END AS overdue
            FROM tasks t LEFT JOIN eucs e ON e.euc_id = t.euc_id
            WHERE {where} AND t.status NOT IN ('Closed','Cancelled')
            """,
            tuple(params),
        )
        findings = dataframe(
            f"""
            SELECT 'Finding' AS item_type, f.finding_id AS item_id, e.reference_id, e.name, e.owner, e.business_unit,
                   f.severity AS category, f.finding_description AS summary, f.assigned_to, NULL AS assigned_role,
                   f.severity AS priority, f.status, f.due_date,
                   CASE WHEN f.due_date IS NOT NULL AND date(f.due_date) < date('now') AND f.status NOT IN ('Closed','Cancelled') THEN 1 ELSE 0 END AS overdue
            FROM findings f JOIN eucs e ON e.euc_id = f.euc_id
            WHERE {where} AND f.status NOT IN ('Closed','Cancelled')
            """,
            tuple(params),
        )
        return pd.concat([tasks, findings], ignore_index=True, sort=False) if not tasks.empty or not findings.empty else pd.DataFrame()
    if report_key == "industrialization_pipeline":
        return dataframe(
            f"""
            SELECT e.reference_id, e.name, e.owner, e.business_unit, e.technology_type, e.frequency,
                   e.inherent_risk, e.residual_risk, e.spof_indicator, e.lifecycle_status,
                   e.industrialization_rationale, e.decommissioning_rationale,
                   COUNT(DISTINCT i.incident_id) AS incident_count,
                   COUNT(DISTINCT CASE WHEN t.status NOT IN ('Closed','Cancelled') THEN t.task_id END) AS open_tasks,
                   (CASE WHEN COALESCE(NULLIF(TRIM(e.bcbs239_output_mapping), ''), '') <> '' THEN 5 ELSE 0 END
                    + CASE WHEN e.residual_risk IN ('High','Very High') THEN 4 ELSE 0 END
                    + CASE WHEN e.spof_indicator = 'Yes' THEN 4 ELSE 0 END
                    + CASE WHEN e.frequency IN ('Daily','Weekly') THEN 3 ELSE 0 END) AS indicative_score
            FROM eucs e
            LEFT JOIN incidents i ON i.euc_id = e.euc_id
            LEFT JOIN tasks t ON t.euc_id = e.euc_id
            WHERE {where} AND (e.lifecycle_status IN ('Industrialization Candidate','Decommissioned','Archived') OR e.residual_risk IN ('High','Very High') OR e.spof_indicator = 'Yes')
            GROUP BY e.euc_id
            ORDER BY indicative_score DESC, e.residual_risk DESC, e.reference_id
            """,
            tuple(params),
        )
    if report_key == "overdue_reviews":
        return dataframe(
            f"""
            SELECT e.reference_id, e.name, e.owner, e.owner_delegate, e.business_unit,
                   e.inherent_risk, e.residual_risk, e.lifecycle_status, e.next_review_date,
                   CAST(julianday(date('now')) - julianday(e.next_review_date) AS INTEGER) AS days_overdue
            FROM eucs e
            WHERE {where} AND e.next_review_date IS NOT NULL AND date(e.next_review_date) < date('now')
            ORDER BY days_overdue DESC, e.residual_risk DESC
            """,
            tuple(params),
        )
    if report_key == "high_criticality_review_coverage":
        return dataframe(
            f"""
            SELECT e.reference_id, e.name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk,
                   e.supports_material_report, e.supports_material_kri, e.supports_material_model,
                   CASE WHEN h.review_id IS NULL THEN 'Missing review' ELSE h.overall_outcome END AS latest_review_outcome,
                   h.review_date, h.reviewer
            FROM eucs e
            LEFT JOIN (
                SELECT h1.* FROM high_criticality_reviews h1
                JOIN (SELECT euc_id, MAX(review_id) AS max_review_id FROM high_criticality_reviews GROUP BY euc_id) latest
                  ON latest.max_review_id = h1.review_id
            ) h ON h.euc_id = e.euc_id
            WHERE {where}
              AND e.inherent_risk IN ('High','Very High')
              AND (e.supports_material_report = 'Yes' OR e.supports_material_kri = 'Yes' OR e.supports_material_model = 'Yes')
            ORDER BY latest_review_outcome DESC, e.inherent_risk DESC, e.reference_id
            """,
            tuple(params),
        )
    if report_key == "documentation_gap_pipeline":
        return dataframe(
            f"""
            SELECT g.gap_id, e.reference_id, e.name, e.owner, e.business_unit, g.gap_area, g.related_artifact,
                   g.severity, g.disposition, g.status, g.target_date, g.owner AS gap_owner, g.closure_comments
            FROM documentation_gaps g JOIN eucs e ON e.euc_id = g.euc_id
            WHERE {where}
            ORDER BY CASE g.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, date(g.target_date)
            """,
            tuple(params),
        )
    if report_key == "lineage_completeness":
        return dataframe(
            f"""
            SELECT e.reference_id, e.name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk,
                   CASE WHEN COALESCE(NULLIF(TRIM(e.inputs), ''), '') <> '' THEN 1 ELSE 0 END AS has_inputs,
                   CASE WHEN COALESCE(NULLIF(TRIM(e.outputs), ''), '') <> '' THEN 1 ELSE 0 END AS has_outputs,
                   CASE WHEN COALESCE(NULLIF(TRIM(e.dependencies), ''), '') <> '' THEN 1 ELSE 0 END AS has_dependencies,
                   CASE WHEN COALESCE(NULLIF(TRIM(e.cde_linkage), ''), '') <> '' THEN 1 ELSE 0 END AS has_cde_linkage,
                   CASE WHEN EXISTS (SELECT 1 FROM components c WHERE c.euc_id = e.euc_id AND COALESCE(NULLIF(TRIM(c.input_sources), ''), '') <> '' AND COALESCE(NULLIF(TRIM(c.data_outputs), ''), '') <> '') THEN 1 ELSE 0 END AS has_asset_lineage,
                   CASE WHEN COALESCE(NULLIF(TRIM(e.inputs), ''), '') <> ''
                         AND COALESCE(NULLIF(TRIM(e.outputs), ''), '') <> ''
                         AND COALESCE(NULLIF(TRIM(e.dependencies), ''), '') <> ''
                         AND COALESCE(NULLIF(TRIM(e.cde_linkage), ''), '') <> ''
                         AND EXISTS (SELECT 1 FROM components c WHERE c.euc_id = e.euc_id AND COALESCE(NULLIF(TRIM(c.input_sources), ''), '') <> '' AND COALESCE(NULLIF(TRIM(c.data_outputs), ''), '') <> '')
                        THEN 'Complete' ELSE 'Incomplete' END AS lineage_status
            FROM eucs e
            WHERE {where} AND e.inherent_risk IN ('High','Very High')
            ORDER BY lineage_status DESC, e.inherent_risk DESC, e.reference_id
            """,
            tuple(params),
        )
    return pd.DataFrame()


def _custom_dataset_df(dataset: str) -> pd.DataFrame:
    if dataset == "EUC Portfolio":
        return dataframe("SELECT * FROM eucs ORDER BY reference_id")
    if dataset == "Tasks":
        return get_tasks(open_only=False)
    if dataset == "Documents / Evidence":
        return dataframe("""
            SELECT d.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk, e.lifecycle_status
            FROM documents d JOIN eucs e ON e.euc_id = d.euc_id ORDER BY d.uploaded_at DESC
        """)
    if dataset == "Risk Assessments":
        return dataframe("""
            SELECT r.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.lifecycle_status
            FROM risk_assessments r JOIN eucs e ON e.euc_id = r.euc_id ORDER BY r.assessment_date DESC, r.assessment_id DESC
        """)
    if dataset == "Findings":
        return dataframe("""
            SELECT f.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk
            FROM findings f JOIN eucs e ON e.euc_id = f.euc_id ORDER BY f.created_at DESC
        """)
    if dataset == "Exceptions":
        return dataframe("""
            SELECT ex.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.inherent_risk
            FROM exceptions ex JOIN eucs e ON e.euc_id = ex.euc_id ORDER BY ex.created_at DESC
        """)
    if dataset == "Incidents":
        return dataframe("""
            SELECT i.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk
            FROM incidents i JOIN eucs e ON e.euc_id = i.euc_id ORDER BY i.incident_date DESC
        """)
    if dataset == "Material Changes":
        return dataframe("""
            SELECT m.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk
            FROM material_changes m JOIN eucs e ON e.euc_id = m.euc_id ORDER BY m.created_at DESC
        """)
    if dataset == "Components / Assets":
        return dataframe("""
            SELECT c.*, e.reference_id, e.name AS euc_name, e.owner AS euc_owner, e.business_unit, e.inherent_risk, e.residual_risk
            FROM components c JOIN eucs e ON e.euc_id = c.euc_id ORDER BY e.reference_id, c.component_name
        """)
    if dataset == "Documentation Gaps":
        return get_documentation_gaps(open_only=False)
    if dataset == "High-Criticality Reviews":
        return get_high_criticality_reviews()
    if dataset == "Industrialization Assessments":
        return get_industrialization_assessments()
    return pd.DataFrame()


def custom_report_dataset_columns(dataset: str) -> list[str]:
    df = _custom_dataset_df(dataset)
    return list(df.columns)


def _apply_custom_filters(df: pd.DataFrame, filters: dict[str, Any] | None) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    filters = filters or {}
    out = df.copy()
    for col, val in filters.items():
        if val in (None, "", "All", []):
            continue
        if col not in out.columns:
            continue
        if isinstance(val, list):
            out = out[out[col].astype(str).isin([str(v) for v in val])]
        else:
            out = out[out[col].astype(str).str.contains(str(val), case=False, na=False)]
    return out


def custom_report_definitions_table(active_only: bool = True) -> pd.DataFrame:
    where = "WHERE active_flag = 1" if active_only else ""
    return dataframe(f"SELECT * FROM custom_report_definitions {where} ORDER BY report_name")


def get_custom_report_definition(report_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM custom_report_definitions WHERE report_id = ?", (report_id,))


def upsert_custom_report_definition(payload: dict[str, Any], username: str, report_id: int | None = None) -> int:
    now = utc_now()
    selected_columns = json.dumps(payload.get("selected_columns") or [], ensure_ascii=False)
    filters_json = json.dumps(payload.get("filters") or {}, ensure_ascii=False)
    if report_id:
        old = get_custom_report_definition(report_id)
        if not old:
            raise ValueError("Custom report definition not found")
        execute(
            """
            UPDATE custom_report_definitions
            SET report_name = ?, description = ?, dataset = ?, selected_columns = ?, filters_json = ?, active_flag = ?, updated_by = ?, updated_at = ?
            WHERE report_id = ?
            """,
            (
                payload.get("report_name"), payload.get("description"), payload.get("dataset"), selected_columns,
                filters_json, 1 if payload.get("active_flag", True) else 0, username, now, report_id,
            ),
        )
        insert_audit("Custom Report", report_id, "UPDATE", username, old, payload)
        return report_id
    report_id = execute(
        """
        INSERT INTO custom_report_definitions(report_name, description, dataset, selected_columns, filters_json, active_flag, created_by, created_at, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("report_name"), payload.get("description"), payload.get("dataset"), selected_columns,
            filters_json, 1 if payload.get("active_flag", True) else 0, username, now, username, now,
        ),
    )
    insert_audit("Custom Report", report_id, "CREATE", username, None, payload)
    return report_id


def run_custom_report_definition(report_id: int) -> pd.DataFrame:
    definition = get_custom_report_definition(report_id)
    if not definition:
        return pd.DataFrame()
    dataset = definition.get("dataset")
    df = _custom_dataset_df(dataset)
    try:
        filters = json.loads(definition.get("filters_json") or "{}")
    except Exception:
        filters = {}
    df = _apply_custom_filters(df, filters)
    try:
        columns = json.loads(definition.get("selected_columns") or "[]")
    except Exception:
        columns = []
    existing_cols = [c for c in columns if c in df.columns]
    if existing_cols:
        df = df[existing_cols]
    return df


def deactivate_custom_report_definition(report_id: int, username: str) -> None:
    old = get_custom_report_definition(report_id)
    if not old:
        return
    execute("UPDATE custom_report_definitions SET active_flag = 0, updated_by = ?, updated_at = ? WHERE report_id = ?", (username, utc_now(), report_id))
    insert_audit("Custom Report", report_id, "DEACTIVATE", username, old, {"active_flag": 0})



def get_documentation_gaps(euc_id: int | None = None, open_only: bool = False) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if euc_id:
        where.append("g.euc_id = ?")
        params.append(euc_id)
    if open_only:
        where.append("g.status NOT IN ('Closed','Cancelled','Accepted Risk')")
    sql = """
        SELECT g.*, e.reference_id, e.name AS euc_name, e.owner AS euc_owner, e.business_unit
        FROM documentation_gaps g JOIN eucs e ON e.euc_id = g.euc_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE g.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, date(g.target_date)"
    return dataframe(sql, tuple(params))


def create_documentation_gap(payload: dict[str, Any], username: str) -> int:
    fields = ["euc_id", "gap_area", "gap_description", "related_artifact", "severity", "owner", "target_date", "disposition", "status", "exception_id", "task_id", "created_by", "created_at", "closure_comments"]
    values = {**payload, "status": payload.get("status", "Open"), "created_by": username, "created_at": utc_now()}
    gap_id = execute(
        f"INSERT INTO documentation_gaps({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(values.get(field) for field in fields),
    )
    task_id = None
    if values.get("disposition") in {"Remediation action", "Remediation", None, ""}:
        task_id = create_task(
            euc_id=payload["euc_id"],
            task_type="Remediation",
            title=f"Close documentation/control gap {gap_id}: {payload.get('gap_area')}",
            description=payload.get("gap_description"),
            assigned_to=payload.get("owner"),
            assigned_role=OWNER_ROLE,
            due_date=payload.get("target_date") or add_days(DEFAULT_DUE_DAYS["Remediation"]),
            priority="High" if payload.get("severity") in {"High", "Critical"} else "Medium",
            username=username,
        )
        execute("UPDATE documentation_gaps SET task_id = ? WHERE gap_id = ?", (task_id, gap_id))
    insert_audit("Documentation Gap", gap_id, "CREATE", username, None, payload)
    queue_raci_notifications("EUC_UPDATED", "Documentation Gap", gap_id, payload["euc_id"], username, context={"Gap area": payload.get("gap_area"), "Severity": payload.get("severity")})
    return gap_id


def update_documentation_gap(gap_id: int, status: str, closure_comments: str, username: str) -> None:
    old = fetch_one("SELECT * FROM documentation_gaps WHERE gap_id = ?", (gap_id,))
    if not old:
        raise ValueError("Documentation gap not found")
    closed_at = utc_now() if status in {"Closed", "Cancelled", "Accepted Risk"} else None
    execute("UPDATE documentation_gaps SET status = ?, closure_comments = ?, closed_at = ? WHERE gap_id = ?", (status, closure_comments, closed_at, gap_id))
    insert_audit("Documentation Gap", gap_id, "UPDATE", username, old, {"status": status, "closure_comments": closure_comments})
    if closed_at and old.get("task_id"):
        close_task_if_open(int(old["task_id"]), username, f"Documentation gap {gap_id} marked {status}.")


def high_criticality_required(euc: dict[str, Any] | None) -> bool:
    if not euc:
        return False
    material = any(str(euc.get(col) or "").strip().lower() == "yes" for col in ("supports_material_report", "supports_material_kri", "supports_material_model"))
    inherent = euc.get("inherent_risk") or "Medium"
    return material and inherent in {"High", "Very High"}


def get_high_criticality_reviews(euc_id: int | None = None) -> pd.DataFrame:
    if euc_id:
        return dataframe("SELECT * FROM high_criticality_reviews WHERE euc_id = ? ORDER BY review_date DESC, review_id DESC", (euc_id,))
    return dataframe("""
        SELECT h.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.inherent_risk, e.residual_risk
        FROM high_criticality_reviews h JOIN eucs e ON e.euc_id = h.euc_id
        ORDER BY h.review_date DESC, h.review_id DESC
    """)


def create_high_criticality_review(payload: dict[str, Any], username: str) -> int:
    fields = [
        "euc_id", "reviewer", "review_date", "mandatory_flag", "overview_governance", "scope_purpose", "lineage_data",
        "design_logic", "controls_reconciliations", "testing_sufficiency", "security_access", "resilience",
        "independent_review_conclusion", "controls_evidence_index", "overall_outcome", "comments", "created_at",
    ]
    values = {**payload, "reviewer": payload.get("reviewer") or username, "review_date": payload.get("review_date") or date.today().isoformat(), "created_at": utc_now()}
    review_id = execute(
        f"INSERT INTO high_criticality_reviews({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(values.get(field) for field in fields),
    )
    insert_audit("High Criticality Review", review_id, "CREATE", username, None, payload)
    queue_raci_notifications("INDEPENDENT_REVIEW_COMPLETED", "High Criticality Review", review_id, payload["euc_id"], username, context={"Outcome": payload.get("overall_outcome")})
    return review_id


def get_industrialization_assessments(euc_id: int | None = None) -> pd.DataFrame:
    if euc_id:
        return dataframe("SELECT * FROM industrialization_assessments WHERE euc_id = ? ORDER BY assessment_date DESC, assessment_id DESC", (euc_id,))
    return dataframe("""
        SELECT a.*, e.reference_id, e.name AS euc_name, e.owner, e.business_unit, e.lifecycle_status
        FROM industrialization_assessments a JOIN eucs e ON e.euc_id = a.euc_id
        ORDER BY a.total_score DESC, a.assessment_date DESC
    """)


def industrialization_priority_band(total_score: int) -> str:
    if total_score >= 10:
        return "Fast-track"
    if total_score >= 7:
        return "Prioritized"
    return "Monitor"


def create_industrialization_assessment(payload: dict[str, Any], username: str) -> int:
    total = sum(int(payload.get(field) or 0) for field in ["bcbs_score", "residual_score", "operational_score", "frequency_volume_score", "strategic_fit_score"])
    values = {**payload, "total_score": total, "priority_band": payload.get("priority_band") or industrialization_priority_band(total), "assessed_by": username, "assessment_date": payload.get("assessment_date") or date.today().isoformat(), "created_at": utc_now()}
    fields = ["euc_id", "bcbs_score", "residual_score", "operational_score", "frequency_volume_score", "strategic_fit_score", "total_score", "priority_band", "decision", "decision_rationale", "assessed_by", "assessment_date", "created_at"]
    assessment_id = execute(
        f"INSERT INTO industrialization_assessments({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(values.get(field) for field in fields),
    )
    insert_audit("Industrialization Assessment", assessment_id, "CREATE", username, None, values)
    queue_raci_notifications("INDUSTRIALIZATION_DECISION", "Industrialization Assessment", assessment_id, payload["euc_id"], username, context={"Total score": total, "Priority band": values.get("priority_band"), "Decision": values.get("decision")})
    return assessment_id


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
    result = {
        "document_type": DOCUMENT_TYPES,
        "lifecycle_status": LIFECYCLE_STATUSES,
        "risk_level": RISK_LEVELS,
        "control_area": CONTROL_AREAS,
        "cacrt_dimension": CACRT_DIMENSIONS,
        "task_type": TASK_TYPES,
        "legal_entity": LEGAL_ENTITIES,
        "business_unit": BUSINESS_UNITS,
        "controlled_storage_type": CONTROLLED_STORAGE_TYPES,
        "level_of_automation": LEVELS_OF_AUTOMATION,
        "bcbs239_output_type": BCBS239_OUTPUT_TYPES,
        "cde_linkage": CDE_LINKAGE_OPTIONS,
    }
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
    queue_raci_notifications(
        "REFERENCE_DATA_UPDATED",
        "Reference Data",
        f"{category}:{value}",
        None,
        username,
        context={"Category": category, "Value": value},
    )


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
    queue_raci_notifications(
        "ARTIFACT_RULE_UPDATED",
        "Required Artifact Rule",
        rule_id,
        None,
        username,
        context={"Risk level": payload.get("risk_level"), "Document type": payload.get("required_document_type")},
    )
    return rule_id


def required_rules_table() -> pd.DataFrame:
    return dataframe("SELECT * FROM required_artifact_rules ORDER BY risk_level, required_document_type")


def due_date_rules_table() -> pd.DataFrame:
    return dataframe("SELECT * FROM due_date_rules ORDER BY task_type, risk_level")




def operational_data_was_purged() -> bool:
    """Return True when an admin has intentionally removed all EUC demo/operational data."""
    row = fetch_one(
        """
        SELECT audit_id
        FROM audit_trail
        WHERE entity_type = 'EUC Operational Data' AND action = 'PURGE'
        ORDER BY audit_id DESC
        LIMIT 1
        """
    )
    return bool(row)


def delete_all_euc_operational_data(username: str) -> dict[str, Any]:
    """Delete all EUC operational data while preserving users and configuration.

    Preserved tables: user_profiles, raci_rules, reference_data,
    required_artifact_rules, due_date_rules, custom_report_definitions, and audit_trail. The audit trail is
    preserved for governance, and this purge action is itself recorded.
    """
    tables_in_delete_order = [
        "notification_outbox",
        "tasks",
        "findings",
        "reviews",
        "exceptions",
        "incidents",
        "material_changes",
        "documents",
        "risk_assessments",
        "components",
        "eucs",
    ]
    counts: dict[str, int] = {}
    for table in tables_in_delete_order:
        row = fetch_one(f"SELECT COUNT(*) AS n FROM {table}")
        counts[table] = int(row["n"] if row else 0)

    for table in tables_in_delete_order:
        execute(f"DELETE FROM {table}")

    # Reset local AUTOINCREMENT counters for the purged operational tables.
    for table in tables_in_delete_order:
        try:
            execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
        except Exception:
            pass

    deleted_upload_items = 0
    UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
    for child in list(UPLOAD_PATH.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        deleted_upload_items += 1

    result = {
        "deleted_rows": counts,
        "deleted_upload_items": deleted_upload_items,
        "preserved": [
            "user_profiles",
            "raci_rules",
            "reference_data",
            "required_artifact_rules",
            "due_date_rules",
            "custom_report_definitions",
            "audit_trail",
        ],
    }
    insert_audit("EUC Operational Data", "ALL", "PURGE", username, counts, result)
    return result


def initialize_reference_data(username: str = "system") -> None:
    seed_required_rules(username)
    seed_bcbs239_outputs(username)
    seed_user_profiles(username)
    seed_raci_rules(username)
    constants = {
        "document_type": DOCUMENT_TYPES,
        "lifecycle_status": LIFECYCLE_STATUSES,
        "risk_level": RISK_LEVELS,
        "control_area": CONTROL_AREAS,
        "cacrt_dimension": CACRT_DIMENSIONS,
        "legal_entity": LEGAL_ENTITIES,
        "business_unit": BUSINESS_UNITS,
        "controlled_storage_type": CONTROLLED_STORAGE_TYPES,
        "level_of_automation": LEVELS_OF_AUTOMATION,
        "bcbs239_output_type": BCBS239_OUTPUT_TYPES,
        "cde_linkage": CDE_LINKAGE_OPTIONS,
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
