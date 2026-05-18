"""Streamlit UI for the End-to-End EUC Governance Monitoring App."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
import json

import pandas as pd
import plotly.express as px
import streamlit as st

import services as svc
from db import DATABASE_FILE, init_db, table_count
from schema import (
    APP_TITLE,
    AUTOMATION_LEVELS,
    BANK_NAME,
    BASELINE_CONTROL_AREAS,
    BCBS_MATERIALITY_QUESTIONS,
    APPROVAL_STATUSES,
    CACRT_DIMENSIONS,
    CHANGE_TYPES,
    CONTROL_AREAS,
    CONTROL_STATUSES,
    CONTROL_STORAGE_TYPES,
    DOCUMENT_STATUSES,
    DOCUMENT_TYPES,
    FINDING_SEVERITIES,
    FREQUENCIES,
    INCIDENT_STATUSES,
    LEGAL_ENTITIES,
    LIFECYCLE_STATUSES,
    OVERALL_STATUSES,
    PRIORITIES,
    REVIEW_OUTCOMES,
    REVIEW_TYPES,
    RISK_ASSESSMENT_TYPES,
    RISK_LEVELS,
    ROLES,
    TASK_STATUSES,
    TASK_TYPES,
    TECHNOLOGY_TYPES,
)
from seed_data import seed_database

st.set_page_config(page_title=APP_TITLE, page_icon="🏦", layout="wide")

NAVIGATION = [
    "Home / Dashboard",
    "EUC Inventory",
    "Register New EUC",
    "EUC Detail View",
    "Components / Assets",
    "Risk Assessment",
    "Documents & Evidence Pack",
    "Required Artifact Checklist",
    "Tasks & Remediation",
    "Data Validation Review Queue",
    "GCC Monitoring View",
    "Findings & Challenge Management",
    "Exceptions",
    "Incidents & Near Misses",
    "Material Changes & Reassessments",
    "Industrialization & Decommissioning",
    "Reports & KPIs",
    "Admin Configuration",
    "Audit Trail",
]


def bootstrap() -> None:
    init_db()
    svc.initialize_reference_data("system")
    if table_count("eucs") == 0:
        seed_database(force=False)


def rerun() -> None:
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()


def current_user() -> tuple[str, str]:
    return st.session_state.get("username", "Demo.User"), st.session_state.get("role", ROLES[0])


def require_write_access() -> bool:
    _, role = current_user()
    if svc.is_read_only(role):
        st.warning("Read-only role: create, update, upload, approval, and closure actions are disabled.")
        return False
    return True


def badge(value: Any) -> str:
    if value is None or value == "":
        return "—"
    value = str(value)
    icon = "⚪"
    if value in {"Complete", "Accepted", "Active", "Low", "Closed", "Approved"}:
        icon = "🟢"
    elif value in {"Medium", "Submitted", "Submitted - Pending Review", "Pending", "In Progress", "Review Ready"}:
        icon = "🟡"
    elif value in {"High", "Very High", "Incomplete", "Rejected", "Expired", "Open", "Critical", "Incident Open", "Under Remediation"}:
        icon = "🔴"
    elif value in {"Decommissioned", "Archived", "Superseded", "Cancelled"}:
        icon = "⚫"
    return f"{icon} {value}"


def safe_df(df: pd.DataFrame, height: int | None = None) -> None:
    if df is None or df.empty:
        st.info("No records found for the current filters.")
    else:
        kwargs = {"use_container_width": True, "hide_index": True}
        # Streamlit 1.50+ rejects height=None, so pass height only when explicitly set.
        if height is not None:
            kwargs["height"] = height
        st.dataframe(df, **kwargs)


def csv_download(df: pd.DataFrame, file_name: str, label: str = "Download CSV") -> None:
    if df is not None and not df.empty:
        st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=file_name, mime="text/csv")


def _first_query_param(name: str) -> str | None:
    try:
        value = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def apply_query_params() -> None:
    """Allow internal evidence-pack links to open an EUC/assessment review."""
    euc_id = _first_query_param("euc_id")
    assessment_id = _first_query_param("assessment_id")
    page = _first_query_param("page")
    if euc_id and str(euc_id).isdigit():
        st.session_state["selected_euc_id"] = int(euc_id)
    if assessment_id and str(assessment_id).isdigit():
        st.session_state["selected_assessment_id"] = int(assessment_id)
    if page in NAVIGATION:
        st.session_state["nav_page"] = page


def assessment_review_url(euc_id: int, assessment_id: int) -> str:
    return f"?page={quote('Risk Assessment')}&euc_id={int(euc_id)}&assessment_id={int(assessment_id)}"


def render_risk_assessment_review(assessment: dict[str, Any] | None) -> None:
    """Business-friendly presentation of a completed risk assessment."""
    if not assessment:
        st.info("No risk assessment selected for review.")
        return
    st.markdown(
        f"**Risk Assessment #{assessment['assessment_id']} · Version {assessment.get('version', '—')}**  \n"
        f"EUC: **{assessment.get('reference_id', '—')} — {assessment.get('euc_name', '—')}**  \n"
        f"Assessed by: **{assessment.get('assessed_by', '—')}** · "
        f"Date: **{assessment.get('assessment_date', '—')}** · "
        f"Type: **{assessment.get('assessment_type') or assessment.get('trigger_type') or '—'}**"
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Materially supports BCBS 239", assessment.get("materially_supports_bcbs239") or "No")
    c2.metric("Overall inherent risk", assessment.get("inherent_risk") or "—")
    c3.metric("Overall residual risk", assessment.get("residual_risk") or "—")

    st.markdown("**Materiality questions**")
    mat = pd.DataFrame(
        [
            {"Question": BCBS_MATERIALITY_QUESTIONS[0], "Answer": assessment.get("materiality_q1")},
            {"Question": BCBS_MATERIALITY_QUESTIONS[1], "Answer": assessment.get("materiality_q2")},
            {"Question": BCBS_MATERIALITY_QUESTIONS[2], "Answer": assessment.get("materiality_q3")},
        ]
    )
    st.dataframe(mat, use_container_width=True, hide_index=True)

    st.markdown("**Dimension calculation**")
    dim = pd.DataFrame(
        [
            {
                "Dimension": "Integrity / Accuracy",
                "Owner inherent": assessment.get("owner_integrity_level"),
                "Effective inherent": assessment.get("effective_integrity_level"),
                "Control effectiveness": assessment.get("integrity_control_effectiveness"),
                "Residual risk": assessment.get("integrity_residual_level"),
                "Rationale": assessment.get("integrity_rationale"),
            },
            {
                "Dimension": "Timeliness / Availability",
                "Owner inherent": assessment.get("owner_timeliness_level"),
                "Effective inherent": assessment.get("effective_timeliness_level"),
                "Control effectiveness": assessment.get("timeliness_control_effectiveness"),
                "Residual risk": assessment.get("timeliness_residual_level"),
                "Rationale": assessment.get("timeliness_rationale"),
            },
        ]
    )
    st.dataframe(dim, use_container_width=True, hide_index=True)

    control_json = assessment.get("control_assessment_json")
    if control_json:
        try:
            controls = pd.DataFrame(json.loads(control_json))
            st.markdown("**Baseline controls**")
            st.dataframe(controls, use_container_width=True, hide_index=True)
        except Exception:
            st.warning("Control-assessment details could not be parsed for this historical record.")
    if assessment.get("required_action_guidance"):
        st.info(assessment["required_action_guidance"])
    if assessment.get("rationale"):
        st.caption(f"Overall notes: {assessment['rationale']}")


def delete_record_panel(entity_type: str, df: pd.DataFrame, id_col: str, label_cols: list[str] | None = None, key: str | None = None) -> None:
    """Render a governed delete widget for GCC and IT Governance Administrator.

    The service layer writes a DELETE audit record with the row snapshot before
    removal. This helper intentionally requires an explicit confirmation tick.
    """
    username, role = current_user()
    if not svc.can_delete_records(role) or df is None or df.empty or id_col not in df.columns:
        return
    label_cols = label_cols or []
    widget_key = key or f"delete_{entity_type}_{id_col}".replace(" ", "_")
    with st.expander(f"Governed delete — {entity_type}"):
        st.warning("Available only to GCC and Group IT Governance Administrator. A DELETE event is retained in the audit trail.")
        options: dict[str, int] = {}
        for _, row in df.dropna(subset=[id_col]).iterrows():
            parts = [f"{id_col}={int(row[id_col])}"]
            for col in label_cols:
                if col in row and pd.notna(row[col]):
                    parts.append(str(row[col])[:80])
            options[" — ".join(parts)] = int(row[id_col])
        if not options:
            st.info("No deletable records are visible in this view.")
            return
        chosen = st.selectbox("Record to delete", list(options.keys()), key=f"{widget_key}_select")
        confirmed = st.checkbox("I understand this will delete the selected record from the MVP database.", key=f"{widget_key}_confirm")
        if st.button(f"Delete selected {entity_type}", key=f"{widget_key}_button", disabled=not confirmed):
            try:
                svc.delete_record(entity_type, options[chosen], username, role)
                st.success(f"Deleted {entity_type} {options[chosen]}. Audit trail retained.")
                rerun()
            except Exception as exc:
                st.error(str(exc))


def option_index(options: list[str], value: str | None, default: int = 0) -> int:
    if value in options:
        return options.index(value)
    return default


def selected_euc_id() -> int | None:
    value = st.session_state.get("selected_euc_id")
    return int(value) if value else None


def euc_selector(label: str = "Select EUC", include_empty: bool = False) -> dict[str, Any] | None:
    username, role = current_user()
    df = svc.all_eucs(role, username)
    if df.empty:
        st.info("No EUCs are available for this user context.")
        return None
    options: dict[str, int | None] = {}
    if include_empty:
        options["—"] = None
    for _, row in df.iterrows():
        options[f"{row['reference_id']} — {row['name']} ({row['owner']})"] = int(row["euc_id"])
    current_id = selected_euc_id()
    labels = list(options.keys())
    default_label = labels[0]
    if current_id:
        for text, euc_id in options.items():
            if euc_id == current_id:
                default_label = text
                break
    chosen = st.selectbox(label, labels, index=labels.index(default_label), key=f"euc_selector_{label}")
    euc_id = options[chosen]
    if euc_id:
        st.session_state["selected_euc_id"] = euc_id
        return svc.get_euc(euc_id)
    return None



def user_select_options(role_filter: str | None = None, include_blank: bool = True) -> list[str]:
    users = svc.user_directory(role=role_filter, active_only=True)
    values = users["username"].tolist() if users is not None and not users.empty else []
    return ([""] if include_blank else []) + values


def can_edit_operational_record(role: str, username: str, euc: dict[str, Any] | None, governance_roles: set[str] | None = None) -> bool:
    if svc.is_read_only(role):
        return False
    governance_roles = governance_roles or {svc.GCC_ROLE, svc.ADMIN_ROLE}
    return svc.can_edit_euc(role, username, euc) or role in governance_roles


def _date_value(value: Any, fallback: date | None = None) -> date:
    fallback = fallback or date.today()
    try:
        if value is None or value == "":
            return fallback
        return pd.to_datetime(value).date()
    except Exception:
        return fallback


def show_login() -> None:
    st.sidebar.markdown(f"### {BANK_NAME}")
    st.sidebar.caption("MVP authentication scaffold")
    role = st.sidebar.selectbox("Role", ROLES, index=ROLES.index(st.session_state.get("role", ROLES[0])))
    suggested = svc.username_options_for_role(role)
    existing = st.session_state.get("username", suggested[0])
    username = st.sidebar.text_input("Username", value=existing if existing else suggested[0])
    if st.sidebar.button("Apply user context", use_container_width=True):
        st.session_state["role"] = role
        st.session_state["username"] = username.strip() or suggested[0]
        st.sidebar.success("User context updated.")
        rerun()
    st.sidebar.caption("Enterprise SSO can replace this block later without changing the service layer.")


def show_sidebar() -> str:
    username, role = current_user()
    st.sidebar.divider()
    st.sidebar.write(f"**Logged in as:** {username}")
    st.sidebar.write(f"**Role:** {role}")
    default_page = st.session_state.get("nav_page", NAVIGATION[0])
    if default_page not in NAVIGATION:
        default_page = NAVIGATION[0]
    page = st.sidebar.radio("Navigation", NAVIGATION, index=NAVIGATION.index(default_page), key="nav_page")
    st.sidebar.divider()
    st.sidebar.caption(f"SQLite: `{DATABASE_FILE.name}` · Uploads: `/uploads`")
    return page


def metric_grid(metrics: dict[str, int]) -> None:
    rows = [list(metrics.items())[i : i + 5] for i in range(0, len(metrics), 5)]
    for row in rows:
        cols = st.columns(len(row))
        for col, (label, value) in zip(cols, row):
            col.metric(label, value)


def page_dashboard() -> None:
    st.title("Home / Dashboard")
    username, role = current_user()
    metrics = svc.dashboard_metrics()
    metric_grid(metrics)

    st.subheader("Portfolio overview")
    data = svc.chart_data()
    c1, c2 = st.columns(2)
    if not data["by_lifecycle"].empty:
        c1.plotly_chart(px.bar(data["by_lifecycle"], x="lifecycle_status", y="count", title="EUCs by lifecycle status"), use_container_width=True)
    if not data["by_risk"].empty:
        c2.plotly_chart(px.pie(data["by_risk"], names="residual_risk", values="count", title="EUCs by residual risk"), use_container_width=True)
    c3, c4 = st.columns(2)
    if not data["by_business_unit"].empty:
        c3.plotly_chart(px.bar(data["by_business_unit"], x="business_unit", y="count", title="EUCs by business unit"), use_container_width=True)
    if not data["tasks_by_status"].empty:
        c4.plotly_chart(px.bar(data["tasks_by_status"], x="status", y="count", title="Tasks by status"), use_container_width=True)

    st.subheader("My task queue")
    tasks = svc.get_tasks(role, username, open_only=True)
    safe_df(tasks[[c for c in ["task_id", "reference_id", "euc_name", "task_type", "title", "due_date", "priority", "status", "overdue"] if c in tasks.columns]], height=260)


def page_inventory() -> None:
    st.title("EUC Inventory")
    username, role = current_user()
    df = svc.all_eucs(role, username)
    if df.empty:
        safe_df(df)
        return
    c1, c2, c3, c4 = st.columns(4)
    owner = c1.selectbox("Owner", ["All"] + sorted(df["owner"].dropna().unique().tolist()))
    unit = c2.selectbox("Business unit", ["All"] + sorted(df["business_unit"].dropna().unique().tolist()))
    risk = c3.selectbox("Residual risk", ["All"] + RISK_LEVELS)
    status = c4.selectbox("Lifecycle status", ["All"] + LIFECYCLE_STATUSES)
    filtered = df.copy()
    if owner != "All":
        filtered = filtered[filtered["owner"] == owner]
    if unit != "All":
        filtered = filtered[filtered["business_unit"] == unit]
    if risk != "All":
        filtered = filtered[filtered["residual_risk"] == risk]
    if status != "All":
        filtered = filtered[filtered["lifecycle_status"] == status]
    show_cols = [
        "euc_id", "reference_id", "name", "purpose", "legal_entity", "business_unit", "owner", "reviewer",
        "supports_material_report", "supports_material_kri", "supports_material_model", "materially_supports_bcbs239",
        "used_by_multiple_bus", "number_active_users", "technology_type", "residual_risk", "lifecycle_status",
        "documentation_completeness_status", "spof_indicator", "next_review_date",
    ]
    show_cols = [c for c in show_cols if c in filtered.columns]
    safe_df(filtered[show_cols], height=500)
    csv_download(filtered[show_cols], "euc_inventory.csv")
    delete_record_panel("EUC", filtered, "euc_id", ["reference_id", "name", "owner"], key="inventory_euc")
    if not filtered.empty:
        selected_ref = st.selectbox("Select EUC record", filtered["reference_id"].tolist())
        row = filtered[filtered["reference_id"] == selected_ref].iloc[0]
        selected = svc.get_euc(int(row["euc_id"]))
        c_open, c_edit = st.columns([1, 3])
        if c_open.button("Set selected EUC / open in Detail View"):
            st.session_state["selected_euc_id"] = int(row["euc_id"])
            st.success(f"Selected {selected_ref}. Use EUC Detail View to continue.")
        if selected and svc.can_edit_euc(role, username, selected):
            with st.expander("Edit selected EUC Inventory record on this page"):
                with st.form(f"inventory_edit_{selected['euc_id']}"):
                    c1, c2, c3 = st.columns(3)
                    name = c1.text_input("EUC Application Name", value=selected.get("name") or "")
                    legal_entity = c2.selectbox("Legal Entity", LEGAL_ENTITIES, index=option_index(LEGAL_ENTITIES, selected.get("legal_entity")))
                    business_unit = c3.text_input("Business Unit", value=selected.get("business_unit") or "")
                    owner_val = c1.text_input("Owner", value=selected.get("owner") or "")
                    delegate = c2.text_input("Owner Delegate", value=selected.get("owner_delegate") or "")
                    reviewer = c3.text_input("Reviewer", value=selected.get("reviewer") or "")
                    purpose = st.text_area("Purpose", value=selected.get("purpose") or "")
                    description = st.text_area("Description", value=selected.get("description") or "")
                    c4, c5, c6 = st.columns(3)
                    tech = c4.selectbox("Technology", TECHNOLOGY_TYPES, index=option_index(TECHNOLOGY_TYPES, selected.get("technology_type")))
                    storage = c5.text_input("Storage location", value=selected.get("storage_location") or "")
                    lifecycle = c6.selectbox("Lifecycle status", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, selected.get("lifecycle_status")))
                    next_review = c4.date_input("Next review date", value=_date_value(selected.get("next_review_date")))
                    spof = c5.selectbox("SPOF indicator", ["No", "Yes"], index=option_index(["No", "Yes"], selected.get("spof_indicator") or "No"))
                    overall = c6.selectbox("Overall status", OVERALL_STATUSES, index=option_index(OVERALL_STATUSES, selected.get("overall_status")))
                    mapping = st.text_area("BCBS 239 output mapping", value=selected.get("bcbs239_output_mapping") or "")
                    if st.form_submit_button("Save selected EUC"):
                        payload = dict(selected)
                        payload.update({
                            "name": name,
                            "legal_entity": legal_entity,
                            "business_unit": business_unit,
                            "owner": owner_val,
                            "owner_delegate": delegate,
                            "reviewer": reviewer,
                            "purpose": purpose,
                            "description": description,
                            "technology_type": tech,
                            "storage_location": storage,
                            "lifecycle_status": lifecycle,
                            "overall_status": overall,
                            "next_review_date": next_review.isoformat() if next_review else None,
                            "spof_indicator": spof,
                            "bcbs239_output_mapping": mapping,
                        })
                        try:
                            svc.update_euc(int(selected["euc_id"]), payload, username)
                            st.success("Selected EUC updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
        elif selected:
            st.info("You can view this EUC but cannot edit it in the current user context.")


def page_register() -> None:
    st.title("Register New EUC")
    username, role = current_user()
    if role not in {svc.OWNER_ROLE, svc.ADMIN_ROLE, svc.CONTRIBUTOR_ROLE}:
        st.warning("Registration is restricted to EUC Owners, Contributors, and Administrators in this MVP.")
        return
    if not require_write_access():
        return

    st.caption("Registration mirrors the uploaded EUC Inventory workbook and can optionally create the first linked EUC Asset Inventory row.")
    with st.form("register_euc"):
        st.subheader("EUC Inventory master record")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("EUC Application Name *")
        legal_entity = c2.selectbox("Legal Entity *", LEGAL_ENTITIES)
        business_unit = c3.text_input("Business Unit *", value="Eurobank Research")
        owner = c1.text_input("Owner *", value=username if role == svc.OWNER_ROLE else "")
        owner_delegate = c2.text_input("Owner Delegate / Contributor")
        reviewer = c3.text_input("Reviewer")
        purpose = st.text_area("EUC Purpose *", help="Corresponds to the EUC Puprose/Purpose column in the workbook.")
        description = st.text_area("Description / business context")

        st.subheader("BCBS 239 and materiality flags")
        c4, c5, c6 = st.columns(3)
        supports_material_report = c4.selectbox("Supports Material Report in scope under Policy 241?", ["Yes", "No"], index=0)
        supports_material_kri = c5.selectbox("Supports Material KRI in scope under Policy 241?", ["Yes", "No"], index=1)
        supports_material_model = c6.selectbox("Supports Material Model in scope under Policy 241?", ["Yes", "No"], index=1)
        bcbs_mapping = st.text_area("RRF Material Report / Material KRI / Material Model mapping *", help="At least one BCBS 239 in-scope output must be mapped.")
        materiality_rationale = st.text_area("Materiality rationale / mapping notes")

        st.subheader("Usage, sourcing, and support")
        c7, c8, c9 = st.columns(3)
        used_by_multiple_bus = c7.selectbox("In use by two or more distinct BUs?", ["No", "Yes"])
        number_active_users = c8.text_input("Number of Active Users", placeholder="e.g., 1, 2+, 10")
        created_by_bu = c9.selectbox("Created by the BU?", ["Yes", "No"])
        acquired_third_party = c7.selectbox("Acquired by third-party / COTS?", ["No", "Yes"])
        support_contract_sla = c8.selectbox("Support contract or SLA in place?", ["No", "Yes"])
        library_of_controls = c9.text_input("Library of Controls link / reference")

        st.subheader("Operating context")
        c10, c11, c12 = st.columns(3)
        technology_type = c10.selectbox("Primary Technology Type *", TECHNOLOGY_TYPES)
        frequency = c11.selectbox("Execution Frequency", FREQUENCIES)
        schedule = c12.text_input("Processing Schedule / Execution Window")
        cut_off = c10.text_input("Cut-off times")
        storage_location = c11.text_input("Controlled Storage Location *", value="SharePoint Server / EUC Library")
        spof = c12.selectbox("Single Point of Failure (SPOF) risk", ["No", "Yes"])
        cde_linkage = st.text_area("CDE Mappings / linkage (optional)")
        inputs = st.text_area("Input sources (systems/files/APIs)")
        outputs = st.text_area("Data Outputs / Produced Files / Reports")
        recipients = st.text_area("Recipients")
        dependencies = st.text_area("Dependencies")
        mapping_na_justification = st.text_area("Not Applicable justification", help="Required if any mapping field is exactly 'Not Applicable'.")

        st.subheader("Review and lifecycle")
        c13, c14, c15 = st.columns(3)
        last_risk_assessment = c13.date_input("Last Risk Assessment", value=date.today())
        next_review_date = c14.date_input("Next Risk Assessment / Review Date", value=date.today() + timedelta(days=90))
        lifecycle_status = c15.selectbox("Initial lifecycle status", ["Draft", "Submitted", "Registered"], index=2)
        exceptions_remediation_actions = st.text_area("Exceptions / Remediation actions")
        industrialization_decommissioning_status = st.text_input("Industrialization / Decommissioning Status")

        st.subheader("Optional first linked EUC Asset Inventory row")
        add_initial_asset = st.checkbox("Create initial asset/component with this EUC", value=True)
        a1, a2, a3 = st.columns(3)
        asset_name = a1.text_input("Files / Asset name", placeholder="e.g., workbook, SQL script, notebook")
        file_description = st.text_area("File description")
        asset_mapping = st.text_area("Asset-level RRF Material Report / KRI / Model Mapping")
        operationalization_link = st.text_input("Operationalization Document Link")
        controlled_storage_type = a2.selectbox("Controlled Storage Type", CONTROL_STORAGE_TYPES)
        level_of_automation = a3.selectbox("Level of Automation", AUTOMATION_LEVELS)
        backup_recovery = st.text_area("Backup / Recovery Arrangements")
        submitted = st.form_submit_button("Register EUC")

    if submitted:
        try:
            duplicates = svc.detect_duplicates(name, owner, business_unit, storage_location)
            euc_id = svc.create_euc(
                {
                    "name": name,
                    "description": description,
                    "purpose": purpose,
                    "legal_entity": legal_entity,
                    "owner": owner,
                    "owner_delegate": owner_delegate,
                    "reviewer": reviewer,
                    "business_unit": business_unit,
                    "technology_type": technology_type,
                    "storage_location": storage_location,
                    "frequency": frequency,
                    "schedule": schedule,
                    "cut_off": cut_off,
                    "business_context": description,
                    "bcbs239_output_mapping": bcbs_mapping,
                    "cde_linkage": cde_linkage,
                    "inputs": inputs,
                    "outputs": outputs,
                    "recipients": recipients,
                    "dependencies": dependencies,
                    "spof_indicator": spof,
                    "supports_material_report": supports_material_report,
                    "supports_material_kri": supports_material_kri,
                    "supports_material_model": supports_material_model,
                    "used_by_multiple_bus": used_by_multiple_bus,
                    "number_active_users": number_active_users,
                    "created_by_bu": created_by_bu,
                    "acquired_third_party": acquired_third_party,
                    "support_contract_sla": support_contract_sla,
                    "library_of_controls": library_of_controls,
                    "last_risk_assessment": last_risk_assessment.isoformat() if last_risk_assessment else None,
                    "exceptions_remediation_actions": exceptions_remediation_actions,
                    "industrialization_decommissioning_status": industrialization_decommissioning_status,
                    "materiality_rationale": materiality_rationale,
                    "lifecycle_status": lifecycle_status,
                    "overall_status": lifecycle_status,
                    "next_review_date": next_review_date.isoformat(),
                    "mapping_na_justification": mapping_na_justification,
                },
                username,
            )
            if add_initial_asset and asset_name.strip():
                svc.create_component(
                    {
                        "euc_id": euc_id,
                        "component_name": asset_name.strip(),
                        "component_type": technology_type,
                        "technology": technology_type,
                        "business_unit": business_unit,
                        "euc_application": name,
                        "material_report_mapping": asset_mapping or bcbs_mapping,
                        "operationalization_document_link": operationalization_link,
                        "storage_location": storage_location,
                        "controlled_storage_type": controlled_storage_type,
                        "input_sources": inputs,
                        "cut_off_times": cut_off,
                        "processing_schedule": schedule,
                        "execution_frequency": frequency,
                        "cde_mappings": cde_linkage,
                        "data_outputs": outputs,
                        "level_of_automation": level_of_automation,
                        "backup_recovery_arrangements": backup_recovery,
                        "spof_risk": spof,
                        "modification_date": date.today().isoformat(),
                        "review_date": next_review_date.isoformat(),
                        "description": file_description,
                        "criticality": "High" if supports_material_report == "Yes" else "Medium",
                        "owner": owner,
                    },
                    username,
                )
            st.session_state["selected_euc_id"] = euc_id
            st.success("EUC Inventory record registered and linked asset/risk-documentation tasks created.")
            if not duplicates.empty:
                st.warning("Potential duplicates detected. Review before continuing.")
                safe_df(duplicates)
        except ValueError as exc:
            st.error(str(exc))

def page_detail() -> None:
    st.title("EUC Detail View")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return
    st.markdown(f"### {euc['reference_id']} — {euc['name']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**Owner:** {euc['owner']}")
    c2.markdown(f"**Risk:** {badge(euc['residual_risk'])}")
    c3.markdown(f"**Lifecycle:** {badge(euc['lifecycle_status'])}")
    c4.markdown(f"**Docs:** {badge(euc['documentation_completeness_status'])}")
    delete_record_panel("EUC", pd.DataFrame([euc]), "euc_id", ["reference_id", "name", "owner"], key="detail_euc")

    tabs = st.tabs(["Overview", "EUC Inventory Fields", "Mapping", "EUC Asset Inventory", "Risk History", "Evidence", "Tasks", "Reviews", "Audit"])
    with tabs[0]:
        st.write(euc.get("description") or "No description recorded.")
        summary_fields = [
            "purpose", "legal_entity", "business_unit", "technology_type", "storage_location", "frequency",
            "schedule", "cut_off", "spof_indicator", "last_risk_assessment", "next_review_date",
            "materially_supports_bcbs239",
        ]
        st.json({k: euc.get(k) for k in summary_fields if k in euc})
        if svc.can_edit_euc(role, username, euc):
            with st.expander("Edit EUC summary and lifecycle"):
                with st.form("edit_euc"):
                    c1, c2, c3 = st.columns(3)
                    name = c1.text_input("Name", value=euc.get("name") or "")
                    legal_entity = c2.selectbox("Legal entity", LEGAL_ENTITIES, index=option_index(LEGAL_ENTITIES, euc.get("legal_entity")))
                    unit = c3.text_input("Business unit", value=euc.get("business_unit") or "")
                    owner = c1.text_input("Owner", value=euc.get("owner") or "")
                    delegate = c2.text_input("Owner delegate", value=euc.get("owner_delegate") or "")
                    reviewer = c3.text_input("Reviewer", value=euc.get("reviewer") or "")
                    tech = c1.selectbox("Technology", TECHNOLOGY_TYPES, index=option_index(TECHNOLOGY_TYPES, euc.get("technology_type")))
                    storage = c2.text_input("Storage location", value=euc.get("storage_location") or "")
                    lifecycle = c3.selectbox("Lifecycle status", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, euc.get("lifecycle_status")))
                    overall = c1.selectbox("Overall status", OVERALL_STATUSES, index=option_index(OVERALL_STATUSES, euc.get("overall_status")))
                    next_review = c2.date_input("Next review date", value=pd.to_datetime(euc.get("next_review_date") or date.today()).date())
                    description = st.text_area("Description", value=euc.get("description") or "")
                    purpose = st.text_area("Purpose", value=euc.get("purpose") or "")
                    if st.form_submit_button("Save changes"):
                        payload = dict(euc)
                        payload.update({
                            "name": name, "legal_entity": legal_entity, "owner": owner, "owner_delegate": delegate,
                            "reviewer": reviewer, "business_unit": unit, "technology_type": tech, "storage_location": storage,
                            "lifecycle_status": lifecycle, "overall_status": overall, "next_review_date": next_review.isoformat(),
                            "description": description, "purpose": purpose,
                        })
                        try:
                            svc.update_euc(euc["euc_id"], payload, username)
                            st.success("EUC updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[1]:
        inventory_fields = [
            "reference_id", "name", "purpose", "legal_entity", "business_unit", "owner", "reviewer",
            "supports_material_report", "supports_material_kri", "supports_material_model", "used_by_multiple_bus",
            "number_active_users", "created_by_bu", "acquired_third_party", "support_contract_sla",
            "library_of_controls", "last_risk_assessment", "next_review_date", "exceptions_remediation_actions",
            "industrialization_decommissioning_status", "inherent_risk", "residual_risk",
        ]
        st.json({k: euc.get(k) for k in inventory_fields if k in euc})
        if svc.can_edit_euc(role, username, euc):
            with st.expander("Edit EUC Inventory workbook fields"):
                with st.form("edit_inventory_workbook_fields"):
                    payload = dict(euc)
                    c1, c2, c3 = st.columns(3)
                    payload["supports_material_report"] = c1.selectbox("Supports Material Report?", ["Yes", "No"], index=option_index(["Yes", "No"], euc.get("supports_material_report")))
                    payload["supports_material_kri"] = c2.selectbox("Supports Material KRI?", ["Yes", "No"], index=option_index(["Yes", "No"], euc.get("supports_material_kri")))
                    payload["supports_material_model"] = c3.selectbox("Supports Material Model?", ["Yes", "No"], index=option_index(["Yes", "No"], euc.get("supports_material_model")))
                    payload["used_by_multiple_bus"] = c1.selectbox("Two or more distinct BUs?", ["No", "Yes"], index=option_index(["No", "Yes"], euc.get("used_by_multiple_bus")))
                    payload["number_active_users"] = c2.text_input("Number of Active Users", value=euc.get("number_active_users") or "")
                    payload["created_by_bu"] = c3.selectbox("Created by BU?", ["Yes", "No"], index=option_index(["Yes", "No"], euc.get("created_by_bu")))
                    payload["acquired_third_party"] = c1.selectbox("Third-party / COTS?", ["No", "Yes"], index=option_index(["No", "Yes"], euc.get("acquired_third_party")))
                    payload["support_contract_sla"] = c2.selectbox("Support contract / SLA?", ["No", "Yes"], index=option_index(["No", "Yes"], euc.get("support_contract_sla")))
                    payload["library_of_controls"] = c3.text_input("Library of Controls", value=euc.get("library_of_controls") or "")
                    payload["exceptions_remediation_actions"] = st.text_area("Exceptions / Remediation actions", value=euc.get("exceptions_remediation_actions") or "")
                    payload["industrialization_decommissioning_status"] = st.text_input("Industrialization / Decommissioning Status", value=euc.get("industrialization_decommissioning_status") or "")
                    if st.form_submit_button("Save EUC Inventory fields"):
                        try:
                            svc.update_euc(euc["euc_id"], payload, username)
                            st.success("Inventory fields updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[2]:
        st.json({k: euc.get(k) for k in ["business_context", "bcbs239_output_mapping", "cde_linkage", "inputs", "outputs", "recipients", "dependencies", "mapping_na_justification", "materiality_rationale"]})
        if svc.can_edit_euc(role, username, euc):
            with st.expander("Edit mapping fields"):
                with st.form("edit_mapping"):
                    payload = dict(euc)
                    for field in ["business_context", "bcbs239_output_mapping", "cde_linkage", "inputs", "outputs", "recipients", "dependencies", "mapping_na_justification", "materiality_rationale"]:
                        payload[field] = st.text_area(field.replace("_", " ").title(), value=euc.get(field) or "")
                    if st.form_submit_button("Save mapping"):
                        try:
                            svc.update_euc(euc["euc_id"], payload, username)
                            st.success("Mapping updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[3]:
        assets_tab = svc.get_components(euc["euc_id"])
        safe_df(assets_tab)
        delete_record_panel("EUC Asset", assets_tab, "component_id", ["component_name", "technology"], key="detail_asset")
    with tabs[4]:
        risk_tab = svc.get_risk_assessments(euc["euc_id"])
        safe_df(risk_tab)
        delete_record_panel("Risk Assessment", risk_tab, "assessment_id", ["version", "assessment_date", "residual_risk"], key="detail_risk")
    with tabs[5]:
        docs_tab = svc.get_documents(euc["euc_id"])
        safe_df(docs_tab)
        delete_record_panel("Document", docs_tab, "document_id", ["document_type", "file_name", "status"], key="detail_document")
    with tabs[6]:
        tasks = svc.get_tasks(open_only=False)
        if not tasks.empty:
            tasks = tasks[tasks["euc_id"] == euc["euc_id"]]
        safe_df(tasks)
        delete_record_panel("Task", tasks, "task_id", ["task_type", "title", "status"], key="detail_task")
    with tabs[7]:
        reviews_tab = svc.get_reviews(euc["euc_id"])
        safe_df(reviews_tab)
        delete_record_panel("Review", reviews_tab, "review_id", ["review_type", "outcome", "reviewer"], key="detail_review")
        if not reviews_tab.empty and role in {svc.DVU_ROLE, svc.GCC_ROLE, svc.ADMIN_ROLE}:
            st.subheader("Edit selected review / add clarification")
            review_map = {f"{int(row['review_id'])} — {row['review_type']} — {row['outcome']} — {row['reviewer']}": int(row["review_id"]) for _, row in reviews_tab.iterrows()}
            chosen_review = st.selectbox("Review record", list(review_map.keys()))
            selected_review = reviews_tab[reviews_tab["review_id"].astype(int) == int(review_map[chosen_review])].iloc[0].to_dict()
            with st.form(f"edit_review_{selected_review['review_id']}"):
                c1, c2, c3 = st.columns(3)
                review_type = c1.selectbox("Review type", REVIEW_TYPES, index=option_index(REVIEW_TYPES, selected_review.get("review_type")))
                outcome = c2.selectbox("Outcome", REVIEW_OUTCOMES, index=option_index(REVIEW_OUTCOMES, selected_review.get("outcome")))
                review_date = c3.date_input("Review date", value=_date_value(selected_review.get("review_date")))
                comments = st.text_area("Comments / clarification", value=selected_review.get("comments") or "")
                if st.form_submit_button("Save selected review"):
                    svc.update_review(int(selected_review["review_id"]), {"review_type": review_type, "outcome": outcome, "comments": comments, "review_date": review_date.isoformat()}, username)
                    st.success("Review updated.")
                    rerun()
    with tabs[8]:
        safe_df(svc.audit_trail({"entity_type": "EUC", "entity_id": euc["euc_id"]}), height=350)

def _asset_payload_from_form(euc: dict[str, Any], username: str, prefix: str, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render asset fields and return payload for create/update."""
    existing = existing or {}
    c1, c2, c3 = st.columns(3)
    component_name = c1.text_input("Files / Asset name *", value=existing.get("component_name") or "", key=f"{prefix}_component_name")
    component_type = c2.selectbox(
        "Component / technology type *",
        TECHNOLOGY_TYPES,
        index=option_index(TECHNOLOGY_TYPES, existing.get("component_type") or euc.get("technology_type")),
        key=f"{prefix}_component_type",
    )
    technology = c3.text_input("Technology", value=existing.get("technology") or euc.get("technology_type") or "", key=f"{prefix}_technology")
    material_mapping = st.text_area(
        "RRF Material Report, Material Report/KRI/Model Mapping",
        value=existing.get("material_report_mapping") or euc.get("bcbs239_output_mapping") or "",
        key=f"{prefix}_material_mapping",
    )
    operationalization_link = st.text_input(
        "Operationalization Document Link",
        value=existing.get("operationalization_document_link") or "",
        key=f"{prefix}_operationalization_link",
    )
    description = st.text_area("File description", value=existing.get("description") or "", key=f"{prefix}_description")
    c4, c5, c6 = st.columns(3)
    controlled_storage_type = c4.selectbox(
        "Controlled Storage Type",
        CONTROL_STORAGE_TYPES,
        index=option_index(CONTROL_STORAGE_TYPES, existing.get("controlled_storage_type")),
        key=f"{prefix}_controlled_storage_type",
    )
    storage_location = c5.text_input(
        "Controlled Storage Location",
        value=existing.get("storage_location") or euc.get("storage_location") or "",
        key=f"{prefix}_storage_location",
    )
    level_of_automation = c6.selectbox(
        "Level of Automation",
        AUTOMATION_LEVELS,
        index=option_index(AUTOMATION_LEVELS, existing.get("level_of_automation")),
        key=f"{prefix}_level_of_automation",
    )
    input_sources = st.text_area("Input sources (systems/files/APIs)", value=existing.get("input_sources") or euc.get("inputs") or "", key=f"{prefix}_input_sources")
    c7, c8, c9 = st.columns(3)
    cut_off_times = c7.text_input("Cut-off times", value=existing.get("cut_off_times") or euc.get("cut_off") or "", key=f"{prefix}_cut_off_times")
    processing_schedule = c8.text_input("Processing Schedule / Execution Window", value=existing.get("processing_schedule") or euc.get("schedule") or "", key=f"{prefix}_processing_schedule")
    execution_frequency = c9.selectbox(
        "Execution Frequency",
        FREQUENCIES,
        index=option_index(FREQUENCIES, existing.get("execution_frequency") or euc.get("frequency")),
        key=f"{prefix}_execution_frequency",
    )
    cde_mappings = st.text_area("CDE Mappings", value=existing.get("cde_mappings") or euc.get("cde_linkage") or "", key=f"{prefix}_cde_mappings")
    data_outputs = st.text_area("Data Outputs / Produced Files / Reports", value=existing.get("data_outputs") or euc.get("outputs") or "", key=f"{prefix}_data_outputs")
    backup = st.text_area("Backup / Recovery Arrangements", value=existing.get("backup_recovery_arrangements") or "", key=f"{prefix}_backup")
    c10, c11, c12, c13 = st.columns(4)
    spof_risk = c10.selectbox("Single Point of Failure (SPOF) risk", ["No", "Yes"], index=option_index(["No", "Yes"], existing.get("spof_risk") or euc.get("spof_indicator")), key=f"{prefix}_spof_risk")
    criticality = c11.selectbox("Criticality", ["Low", "Medium", "High", "Critical"], index=option_index(["Low", "Medium", "High", "Critical"], existing.get("criticality") or ("High" if euc.get("residual_risk") in {"High", "Very High"} else "Medium")), key=f"{prefix}_criticality")
    asset_owner = c12.text_input("Asset Owner", value=existing.get("owner") or euc.get("owner") or username, key=f"{prefix}_asset_owner")
    default_review = pd.to_datetime(existing.get("review_date") or euc.get("next_review_date") or date.today()).date()
    review_date = c13.date_input("Review Date", value=default_review, key=f"{prefix}_review_date")
    default_mod = pd.to_datetime(existing.get("modification_date") or date.today()).date()
    modification_date = st.date_input("Modification Date", value=default_mod, key=f"{prefix}_modification_date")
    return {
        "euc_id": euc["euc_id"],
        "component_name": component_name,
        "component_type": component_type,
        "technology": technology,
        "business_unit": euc.get("business_unit"),
        "euc_application": euc.get("name"),
        "material_report_mapping": material_mapping,
        "operationalization_document_link": operationalization_link,
        "storage_location": storage_location,
        "controlled_storage_type": controlled_storage_type,
        "input_sources": input_sources,
        "cut_off_times": cut_off_times,
        "processing_schedule": processing_schedule,
        "execution_frequency": execution_frequency,
        "cde_mappings": cde_mappings,
        "data_outputs": data_outputs,
        "level_of_automation": level_of_automation,
        "backup_recovery_arrangements": backup,
        "spof_risk": spof_risk,
        "modification_date": modification_date.isoformat(),
        "review_date": review_date.isoformat(),
        "criticality": criticality,
        "owner": asset_owner,
        "description": description,
    }


def page_components() -> None:
    st.title("Components / EUC Asset Inventory")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return
    st.caption("Each asset row is explicitly linked to the selected EUC through euc_id and mirrors the uploaded EUC Asset Inventory workbook.")
    assets = svc.get_components(euc["euc_id"])
    preferred_cols = [
        "component_id", "reference_id", "euc_name", "business_unit", "component_name", "description", "technology",
        "controlled_storage_type", "storage_location", "input_sources", "cut_off_times", "processing_schedule",
        "execution_frequency", "cde_mappings", "data_outputs", "level_of_automation", "backup_recovery_arrangements",
        "spof_risk", "modification_date", "review_date", "owner",
    ]
    visible_assets = assets[[c for c in preferred_cols if c in assets.columns]] if not assets.empty else assets
    safe_df(visible_assets, height=350)
    delete_record_panel("EUC Asset", assets, "component_id", ["component_name", "technology", "owner"], key="components_asset")

    if not assets.empty:
        st.subheader("Select and edit EUC Asset Inventory row")
        options = {
            f"{int(row['component_id'])} — {row['component_name']} — {row.get('technology') or 'n/a'}": int(row["component_id"])
            for _, row in assets.iterrows()
        }
        selected_label = st.selectbox("Asset row from table", list(options.keys()))
        selected_asset = svc.get_component(options[selected_label])
        if selected_asset:
            with st.expander("Edit selected asset", expanded=True):
                if svc.can_edit_euc(role, username, euc):
                    with st.form("edit_component"):
                        payload = _asset_payload_from_form(euc, username, "edit_asset", selected_asset)
                        if st.form_submit_button("Save selected asset changes"):
                            try:
                                svc.update_component(int(selected_asset["component_id"]), payload, username)
                                st.success("Selected EUC asset row updated.")
                                rerun()
                            except ValueError as exc:
                                st.error(str(exc))
                else:
                    st.json({k: selected_asset.get(k) for k in preferred_cols if k in selected_asset})

    if not svc.can_edit_euc(role, username, euc):
        st.info("You can view assets but cannot add or edit assets for this EUC in the current role.")
        return
    with st.expander("Add new EUC Asset Inventory row", expanded=assets.empty):
        with st.form("add_component"):
            payload = _asset_payload_from_form(euc, username, "add_asset")
            if st.form_submit_button("Add asset"):
                if not payload["component_name"]:
                    st.error("Files / Asset name is required.")
                else:
                    svc.create_component(payload, username)
                    st.success("EUC asset row added and linked to the selected EUC.")
                    rerun()


def page_risk_assessment() -> None:
    st.title("Risk Assessment")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return
    st.info("This page implements the uploaded EUC Risk Assessment workbook: materiality questions, two inherent risk dimensions, eight baseline controls, derived control effectiveness, and the residual-risk matrix.")
    assessments = svc.get_risk_assessments(euc["euc_id"])
    display_cols = [
        "assessment_id", "version", "assessment_date", "assessed_by", "assessment_type",
        "materially_supports_bcbs239", "owner_integrity_level", "owner_timeliness_level",
        "effective_integrity_level", "effective_timeliness_level", "integrity_control_effectiveness",
        "timeliness_control_effectiveness", "integrity_residual_level", "timeliness_residual_level",
        "inherent_risk", "residual_risk", "required_action_guidance",
    ]
    visible_assessments = assessments[[c for c in display_cols if c in assessments.columns]] if not assessments.empty else assessments
    safe_df(visible_assessments, height=280)
    selected_assessment_id = st.session_state.get("selected_assessment_id")
    if not assessments.empty:
        assessment_map = {
            f"#{int(row['assessment_id'])} v{int(row['version'])} — {row['assessment_date']} — residual {row['residual_risk']}": int(row["assessment_id"])
            for _, row in assessments.iterrows()
        }
        labels = list(assessment_map.keys())
        default_index = 0
        if selected_assessment_id and int(selected_assessment_id) in list(assessment_map.values()):
            default_index = list(assessment_map.values()).index(int(selected_assessment_id))
        chosen_assessment = st.selectbox("Select completed assessment for review / superseding reference", labels, index=default_index)
        selected_assessment_id = assessment_map[chosen_assessment]
        selected_assessment = svc.get_risk_assessment(int(selected_assessment_id))
        if selected_assessment and int(selected_assessment.get("euc_id", 0)) == int(euc["euc_id"]):
            with st.expander(f"Assessment review — #{selected_assessment_id}", expanded=False):
                render_risk_assessment_review(selected_assessment)
            st.caption("Completed assessments are not overwritten. To amend one, submit a new assessment below; it will be stored as the next version.")
    delete_record_panel("Risk Assessment", assessments, "assessment_id", ["version", "assessment_date", "inherent_risk", "residual_risk"], key="risk_assessment")
    if not svc.can_edit_euc(role, username, euc) and role not in {svc.ADMIN_ROLE, svc.GCC_ROLE}:
        st.warning("Only the EUC owner/delegate or governance roles can record assessments.")
        return

    with st.form("risk_assessment"):
        st.subheader("Assessment header")
        c1, c2, c3 = st.columns(3)
        assessment_type = c1.selectbox("Assessment Type", RISK_ASSESSMENT_TYPES)
        assessment_date = c2.date_input("Assessment Date", value=date.today())
        assessed_by = c3.text_input("Assessed by", value=username)

        st.subheader("BCBS 239 materiality assessment")
        default_material = "Yes" if euc.get("materially_supports_bcbs239") == "Yes" or euc.get("supports_material_report") == "Yes" else "No"
        q1 = st.selectbox(BCBS_MATERIALITY_QUESTIONS[0], ["Yes", "No"], index=option_index(["Yes", "No"], default_material))
        q2 = st.selectbox(BCBS_MATERIALITY_QUESTIONS[1], ["Yes", "No"], index=option_index(["Yes", "No"], "Yes" if euc.get("supports_material_kri") == "Yes" else "No"))
        q3 = st.selectbox(BCBS_MATERIALITY_QUESTIONS[2], ["Yes", "No"], index=option_index(["Yes", "No"], euc.get("spof_indicator") or "No"))
        st.caption("If any answer is Yes, the effective inherent risk for both dimensions is forced to Very High, matching the workbook.")

        st.subheader("Inherent risk by dimension")
        c4, c5 = st.columns(2)
        owner_level_options = ["Low", "Medium", "High"]
        materiality_forces_very_high = any(v == "Yes" for v in [q1, q2, q3])
        if materiality_forces_very_high:
            st.warning(
                "At least one BCBS 239 materiality answer is Yes. Per the workbook, owner input remains Low/Medium/High, "
                "but both effective inherent-risk dimensions are automatically calculated as Very High."
            )
        owner_integrity = c4.selectbox(
            "Owner inherent level — Integrity / Accuracy",
            owner_level_options,
            index=option_index(owner_level_options, euc.get("inherent_risk") if euc.get("inherent_risk") in owner_level_options else "Medium"),
            help="Workbook input B22. Very High is not manually selectable; it is derived from BCBS 239 materiality.",
        )
        owner_timeliness = c5.selectbox(
            "Owner inherent level — Timeliness / Availability",
            owner_level_options,
            index=option_index(owner_level_options, euc.get("inherent_risk") if euc.get("inherent_risk") in owner_level_options else "Medium"),
            help="Workbook input B23. Very High is not manually selectable; it is derived from BCBS 239 materiality.",
        )
        if materiality_forces_very_high:
            c4.metric("Effective Integrity / Accuracy inherent risk", "Very High")
            c5.metric("Effective Timeliness / Availability inherent risk", "Very High")
        integrity_rationale = c4.text_area("Integrity / Accuracy rationale")
        timeliness_rationale = c5.text_area("Timeliness / Availability rationale")

        st.subheader("Baseline control assessment")
        st.caption("Control effectiveness is derived automatically using the workbook formula: multiple missing controls drive Not in place/Weak; evidenced controls drive Adequate/Strong.")
        controls = {}
        default_by_control = {
            "1. Registration & risk assessment": "In place and evidenced",
            "2. Privileged Access": "Partially in place",
            "3. Versioning & change log": "In place and evidenced",
            "4. Checks & reconciliations": "In place and evidenced",
            "5. EUC Library of Controls (CACRT)": "In place and evidenced" if euc.get("residual_risk") in {"High", "Very High"} else "N/A",
            "6. Operating Procedure": "In place and evidenced",
            "7. Evidence & sign-off": "Partially in place",
            "8. Resilience": "In place and evidenced" if euc.get("spof_indicator") == "No" else "Partially in place",
        }
        for control in BASELINE_CONTROL_AREAS:
            c_status, c_rationale = st.columns([1, 2])
            status_options = CONTROL_STATUSES if control in svc.NA_ALLOWED_CONTROL_KEYS else [s for s in CONTROL_STATUSES if s != "N/A"]
            default_status = default_by_control.get(control, "In place and evidenced")
            if default_status not in status_options:
                default_status = "In place and evidenced"
            status = c_status.selectbox(
                control,
                status_options,
                index=option_index(status_options, default_status),
                key=f"risk_{euc['euc_id']}_{control}",
            )
            rationale = c_rationale.text_input(f"Rationale / evidence notes — {control}", key=f"risk_note_{euc['euc_id']}_{control}")
            controls[control] = {"status": status, "rationale": rationale}

        rationale = st.text_area("Overall assessment rationale / notes")
        if st.form_submit_button("Submit policy risk assessment"):
            assessment_id = svc.create_risk_assessment(
                {
                    "euc_id": euc["euc_id"],
                    "assessment_date": assessment_date.isoformat(),
                    "assessed_by": assessed_by,
                    "assessment_type": assessment_type,
                    "trigger_type": assessment_type,
                    "materiality_q1": q1,
                    "materiality_q2": q2,
                    "materiality_q3": q3,
                    "owner_integrity_level": owner_integrity,
                    "owner_timeliness_level": owner_timeliness,
                    "integrity_rationale": integrity_rationale,
                    "timeliness_rationale": timeliness_rationale,
                    "controls": controls,
                    "rationale": rationale,
                },
                username,
            )
            st.success(f"Assessment {assessment_id} submitted. Effective inherent risk, residual risk, and required artifact completeness were recalculated.")
            rerun()

def page_documents() -> None:
    st.title("Documents & Evidence Pack")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return

    st.subheader("Required Artifact Checklist")
    st.markdown(f"Residual risk: **{badge(euc['residual_risk'])}** · Completeness: **{badge(euc['documentation_completeness_status'])}**")
    checklist = svc.artifact_checklist(euc["euc_id"])
    checklist_cols = ["document_type", "mandatory", "status", "document_id", "reviewed_by", "comments"]
    safe_df(checklist[[c for c in checklist_cols if c in checklist.columns]] if not checklist.empty else checklist, height=260)
    c_check1, c_check2 = st.columns(2)
    if c_check1.button("Recalculate evidence completeness"):
        status = svc.evaluate_and_update_completeness(euc["euc_id"], username, create_missing_tasks=False)
        st.success(f"Completeness status: {status}")
        rerun()
    if c_check2.button("Create tasks for missing/rejected mandatory artifacts", disabled=svc.is_read_only(role)):
        status = svc.evaluate_and_update_completeness(euc["euc_id"], username, create_missing_tasks=True)
        st.success(f"Follow-up tasks checked/created. Completeness status: {status}")
        rerun()

    st.divider()
    st.subheader("Risk assessment evidence")
    assessments = svc.get_risk_assessments(euc["euc_id"])
    if assessments.empty:
        st.warning("No completed risk assessment exists for this EUC. Complete the Risk Assessment page; do not upload a risk assessment document.")
    else:
        st.caption("Completed risk assessments are treated as evidence directly from the Risk Assessment module.")
        link_rows = []
        for _, row in assessments.iterrows():
            review_url = assessment_review_url(int(euc["euc_id"]), int(row["assessment_id"]))
            link_rows.append(
                {
                    "assessment_id": int(row["assessment_id"]),
                    "version": int(row["version"]),
                    "assessment_date": row.get("assessment_date"),
                    "assessed_by": row.get("assessed_by"),
                    "material_bcbs239": row.get("materially_supports_bcbs239"),
                    "overall_inherent_risk": row.get("inherent_risk"),
                    "overall_residual_risk": row.get("residual_risk"),
                    "review_link": review_url,
                }
            )
        st.dataframe(
            pd.DataFrame(link_rows),
            use_container_width=True,
            hide_index=True,
            column_config={"review_link": st.column_config.LinkColumn("Review link", display_text="Open assessment")},
        )
        assessment_options = {
            f"#{int(row['assessment_id'])} v{int(row['version'])} — {row['assessment_date']} — residual {row['residual_risk']}": int(row["assessment_id"])
            for _, row in assessments.iterrows()
        }
        selected_from_query = st.session_state.get("selected_assessment_id")
        default_index = 0
        if selected_from_query in assessment_options.values():
            default_index = list(assessment_options.values()).index(selected_from_query)
        selected_label = st.selectbox("Present assessment for review in Evidence Pack", list(assessment_options.keys()), index=default_index)
        with st.expander("Selected Risk Assessment review", expanded=bool(selected_from_query)):
            render_risk_assessment_review(svc.get_risk_assessment(assessment_options[selected_label]))

    st.divider()
    st.subheader("Uploaded document evidence")
    docs = svc.get_documents(euc["euc_id"])
    doc_cols = ["document_id", "document_type", "file_name", "status", "uploaded_by", "uploaded_at", "reviewed_by", "reviewed_at", "comments", "deficiency_tag"]
    safe_df(docs[[c for c in doc_cols if c in docs.columns]] if not docs.empty else docs, height=320)
    delete_record_panel("Document", docs, "document_id", ["document_type", "file_name", "status"], key="documents_document")
    st.caption("Upload only the evidence type and file. Status is assigned automatically as Submitted, then updated by GCC/Data Validation review. Risk Assessment comes from the Risk Assessment module.")

    tabs = st.tabs(["Upload evidence", "Edit / review selected evidence"])
    with tabs[0]:
        if svc.can_upload_evidence(role, username, euc) and require_write_access():
            uploaded = st.file_uploader("Upload document / evidence")
            with st.form("doc_metadata"):
                uploadable_document_types = [doc_type for doc_type in DOCUMENT_TYPES if doc_type != "Risk Assessment"]
                document_type = st.selectbox("Document type", uploadable_document_types)
                comments = st.text_area("Comments")
                st.info("Initial status will be set automatically to Submitted.")
                if st.form_submit_button("Save uploaded evidence"):
                    if uploaded is None:
                        st.error("Select a file before saving metadata.")
                    else:
                        file_name, file_path = svc.save_document_file(euc["euc_id"], uploaded.name, uploaded.getvalue())
                        doc_id = svc.create_document_record(
                            {
                                "euc_id": euc["euc_id"],
                                "file_name": file_name,
                                "file_path": file_path,
                                "document_type": document_type,
                                "status": "Submitted",
                                "comments": comments,
                            },
                            username,
                        )
                        st.success(f"Evidence uploaded as document {doc_id}. Status: Submitted.")
                        rerun()
        else:
            st.info("Upload is disabled for the current role/EUC relationship.")

    with tabs[1]:
        if docs.empty:
            st.info("No uploaded evidence exists for this EUC.")
        else:
            doc_map = {f"{int(row['document_id'])} — {row['document_type']} — {row['file_name']} — {row['status']}": int(row["document_id"]) for _, row in docs.iterrows()}
            chosen = st.selectbox("Evidence record", list(doc_map.keys()))
            selected = docs[docs["document_id"].astype(int) == int(doc_map[chosen])].iloc[0].to_dict()
            can_meta_edit = svc.can_upload_evidence(role, username, euc) and (selected.get("status") not in {"Accepted"} or role in {svc.GCC_ROLE, svc.ADMIN_ROLE})
            can_review_doc = svc.can_review(role)
            if not (can_meta_edit or can_review_doc) or svc.is_read_only(role):
                st.info("You can view this evidence record but cannot update it in the current role.")
                st.json({k: selected.get(k) for k in doc_cols if k in selected})
            else:
                with st.form(f"edit_doc_{selected['document_id']}"):
                    uploadable_document_types = [doc_type for doc_type in DOCUMENT_TYPES if doc_type != "Risk Assessment"]
                    document_type = st.selectbox(
                        "Document type",
                        uploadable_document_types,
                        index=option_index(uploadable_document_types, selected.get("document_type")),
                        disabled=not can_meta_edit,
                    )
                    comments = st.text_area("Comments", value=selected.get("comments") or "", disabled=not (can_meta_edit or can_review_doc))
                    deficiency = st.text_input("Deficiency tag", value=selected.get("deficiency_tag") or "", disabled=not can_review_doc)
                    status = st.selectbox(
                        "Status",
                        ["Submitted", "Accepted", "Rejected", "Expired", "Superseded"],
                        index=option_index(["Submitted", "Accepted", "Rejected", "Expired", "Superseded"], selected.get("status")),
                        disabled=not can_review_doc,
                    )
                    st.caption(f"File: {selected.get('file_name')} · Uploaded by {selected.get('uploaded_by')} on {selected.get('uploaded_at')}")
                    if st.form_submit_button("Save selected evidence record"):
                        try:
                            svc.update_document_metadata(
                                int(selected["document_id"]),
                                {"document_type": document_type, "comments": comments, "deficiency_tag": deficiency, "status": status},
                                username,
                                review_update=can_review_doc,
                            )
                            st.success("Evidence record updated and checklist recalculated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))


def page_checklist() -> None:
    st.title("Required Artifact Checklist")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return
    st.markdown(f"Residual risk: **{badge(euc['residual_risk'])}** · Lifecycle: **{badge(euc['lifecycle_status'])}**")
    checklist = svc.artifact_checklist(euc["euc_id"])
    safe_df(checklist, height=350)
    c1, c2 = st.columns(2)
    if c1.button("Recalculate completeness"):
        status = svc.evaluate_and_update_completeness(euc["euc_id"], username, create_missing_tasks=False)
        st.success(f"Completeness status: {status}")
        rerun()
    if c2.button("Create follow-up tasks for missing/rejected mandatory artifacts", disabled=svc.is_read_only(role)):
        status = svc.evaluate_and_update_completeness(euc["euc_id"], username, create_missing_tasks=True)
        st.success(f"Tasks checked/created. Completeness status: {status}")
        rerun()
    st.caption("Overrides for missing mandatory artifacts should be managed through the exception workflow.")


def page_tasks() -> None:
    st.title("Tasks & Remediation")
    username, role = current_user()
    st.caption("Select an EUC first. The task table is filtered to the selected EUC and current user/role visibility.")
    euc = euc_selector("Select EUC for task review")
    if not euc:
        return
    open_only = st.toggle("Open tasks only", value=True)
    tasks = svc.get_tasks(role, username, open_only=open_only, euc_id=euc["euc_id"])
    preferred_cols = [
        "task_id", "reference_id", "euc_name", "task_type", "title", "description",
        "assigned_to", "assigned_full_name", "assigned_email", "assigned_role",
        "due_date", "overdue", "priority", "status", "closure_reason",
        "closure_evidence_document_id", "created_at", "closed_at",
    ]
    visible_tasks = tasks[[c for c in preferred_cols if c in tasks.columns]] if not tasks.empty else tasks
    safe_df(visible_tasks, height=420)
    delete_record_panel("Task", tasks, "task_id", ["task_type", "title", "status"], key="tasks_task")
    if tasks.empty or svc.is_read_only(role):
        return

    st.subheader("Select and edit task")
    task_map = {f"{int(row['task_id'])} — {row['title']} — {row['status']}": int(row["task_id"]) for _, row in tasks.iterrows()}
    chosen = st.selectbox("Task", list(task_map.keys()))
    selected = svc.get_task(task_map[chosen])
    if not selected:
        st.warning("The selected task no longer exists.")
        return
    governance_editor = role in {svc.GCC_ROLE, svc.DVU_ROLE, svc.ADMIN_ROLE}
    assigned_editor = selected.get("assigned_to") == username or selected.get("assigned_role") == role
    owner_editor = svc.can_edit_euc(role, username, euc)
    if not (governance_editor or assigned_editor or owner_editor):
        st.info("You can view this task but cannot edit it in the current user context.")
        return

    with st.form(f"edit_task_{selected['task_id']}"):
        c1, c2, c3 = st.columns(3)
        task_type = c1.selectbox("Task type", TASK_TYPES, index=option_index(TASK_TYPES, selected.get("task_type")), disabled=not governance_editor)
        priority = c2.selectbox("Priority", PRIORITIES, index=option_index(PRIORITIES, selected.get("priority")), disabled=not governance_editor)
        status = c3.selectbox("Status", TASK_STATUSES, index=option_index(TASK_STATUSES, selected.get("status")))
        title = st.text_input("Title", value=selected.get("title") or "", disabled=not governance_editor)
        description = st.text_area("Description", value=selected.get("description") or "", disabled=not governance_editor)
        c4, c5, c6 = st.columns(3)
        users = user_select_options(include_blank=True)
        if selected.get("assigned_to") and selected.get("assigned_to") not in users:
            users.append(selected.get("assigned_to"))
        assigned_to = c4.selectbox("Assigned user", users, index=option_index(users, selected.get("assigned_to"), 0), disabled=not governance_editor)
        assigned_role = c5.selectbox("Assigned role", ROLES, index=option_index(ROLES, selected.get("assigned_role")), disabled=not governance_editor)
        due_date = c6.date_input("Due date", value=_date_value(selected.get("due_date")), disabled=not governance_editor)
        evidence_id = st.number_input("Closure evidence document ID", min_value=0, value=int(selected.get("closure_evidence_document_id") or 0), step=1)
        reason = st.text_area("Closure reason / response", value=selected.get("closure_reason") or "")
        if st.form_submit_button("Save selected task"):
            payload = {
                "task_type": task_type,
                "title": title,
                "description": description,
                "assigned_to": assigned_to or None,
                "assigned_role": assigned_role,
                "due_date": due_date.isoformat() if due_date else None,
                "status": status,
                "priority": priority,
                "closure_reason": reason,
                "closure_evidence_document_id": int(evidence_id) or None,
            }
            try:
                svc.update_task_full(int(selected["task_id"]), payload, username)
                st.success("Task updated.")
                rerun()
            except ValueError as exc:
                st.error(str(exc))


def page_dvu_queue() -> None:
    st.title("Data Validation Review Queue")
    username, role = current_user()
    if role not in {svc.DVU_ROLE, svc.ADMIN_ROLE}:
        st.warning("This queue is restricted to Data Validation and Administrator roles.")
        return
    queue = svc.data_validation_queue()
    safe_df(queue, height=360)
    if queue.empty or svc.is_read_only(role):
        return
    st.subheader("Record Data Validation review")
    euc_map = {f"{row['reference_id']} — {row['name']}": int(row["euc_id"]) for _, row in queue.iterrows()}
    chosen = st.selectbox("Review EUC", list(euc_map.keys()))
    euc_id = euc_map[chosen]
    with st.form("dvu_review"):
        outcome = st.selectbox("Outcome", REVIEW_OUTCOMES)
        comments = st.text_area("Comments / challenge outcome")
        raise_finding = st.checkbox("Create finding from review") or outcome == "Finding raised"
        severity = st.selectbox("Finding severity", FINDING_SEVERITIES, index=2)
        requirement = st.text_input("Requirement", value="Data Validation")
        finding_text = st.text_area("Finding description")
        due_date = st.date_input("Remediation due date", value=date.today() + timedelta(days=30))
        if st.form_submit_button("Submit review"):
            try:
                review_id = svc.create_review({"euc_id": euc_id, "review_type": "Data Validation", "outcome": outcome, "comments": comments}, username, role)
                if raise_finding:
                    euc = svc.get_euc(euc_id)
                    svc.create_finding({"euc_id": euc_id, "review_id": review_id, "severity": severity, "requirement": requirement, "control_area": "Data Validation", "finding_description": finding_text or comments or "Data Validation challenge raised.", "remediation_required": comments, "assigned_to": euc.get("owner") if euc else None, "due_date": due_date.isoformat(), "status": "Open"}, username)
                st.success("Review recorded.")
                rerun()
            except ValueError as exc:
                st.error(str(exc))


def page_gcc() -> None:
    st.title("GCC Monitoring View")
    username, role = current_user()
    if role not in {svc.GCC_ROLE, svc.ADMIN_ROLE, svc.READ_ONLY_ROLE}:
        st.warning("GCC monitoring is visible to GCC, Administrator, and Internal Audit roles.")
        return
    data = svc.gcc_monitoring_dataset()
    if not data["risk_distribution"].empty:
        st.plotly_chart(px.bar(data["risk_distribution"], x="residual_risk", y="count", title="Portfolio risk distribution"), use_container_width=True)
    tabs = st.tabs(["Missing documentation", "Overdue tasks", "Open findings", "Open exceptions", "Open incidents", "High / Very High", "SPOF", "Industrialization", "Decommissioning"])
    for tab, key in zip(tabs, ["missing_documentation", "overdue_tasks", "open_findings", "open_exceptions", "open_incidents", "high_risk", "spof", "industrialization", "decommissioning"]):
        with tab:
            safe_df(data[key], height=350)


def page_findings() -> None:
    st.title("Findings & Challenge Management")
    username, role = current_user()
    findings = svc.get_findings(open_only=False)
    safe_df(findings, height=350)
    delete_record_panel("Finding", findings, "finding_id", ["reference_id", "severity", "status"], key="findings_finding")
    if svc.is_read_only(role):
        return
    tabs = st.tabs(["Raise finding", "Edit selected finding"])
    with tabs[0]:
        if role not in {svc.DVU_ROLE, svc.GCC_ROLE, svc.ADMIN_ROLE}:
            st.info("Only Data Validation, GCC, and Administrator roles can raise findings.")
        else:
            euc = euc_selector("Finding EUC")
            if euc:
                with st.form("raise_finding"):
                    severity = st.selectbox("Severity", FINDING_SEVERITIES)
                    requirement = st.text_input("Requirement")
                    control_area = st.selectbox("Control area", CONTROL_AREAS)
                    description = st.text_area("Finding description *")
                    remediation = st.text_area("Remediation required")
                    users = user_select_options(include_blank=True)
                    if euc.get("owner") and euc.get("owner") not in users:
                        users.append(euc.get("owner"))
                    assigned_to = st.selectbox("Assigned owner", users, index=option_index(users, euc.get("owner"), 0))
                    due = st.date_input("Due date", value=date.today() + timedelta(days=30))
                    if st.form_submit_button("Create finding"):
                        if not description:
                            st.error("Finding description is required.")
                        else:
                            svc.create_finding({"euc_id": euc["euc_id"], "severity": severity, "requirement": requirement, "control_area": control_area, "finding_description": description, "remediation_required": remediation, "assigned_to": assigned_to, "due_date": due.isoformat(), "status": "Open"}, username)
                            st.success("Finding created and remediation task assigned.")
                            rerun()
    with tabs[1]:
        if findings.empty:
            st.info("No findings to update.")
        else:
            finding_map = {f"{int(row['finding_id'])} — {row['reference_id']} — {row['severity']} — {row['status']}": int(row["finding_id"]) for _, row in findings.iterrows()}
            chosen = st.selectbox("Finding", list(finding_map.keys()))
            selected = findings[findings["finding_id"].astype(int) == int(finding_map[chosen])].iloc[0].to_dict()
            euc = svc.get_euc(int(selected["euc_id"]))
            governance_editor = role in {svc.DVU_ROLE, svc.GCC_ROLE, svc.ADMIN_ROLE}
            owner_editor = svc.can_edit_euc(role, username, euc)
            if not (governance_editor or owner_editor):
                st.info("You can view this finding but cannot update it in the current role.")
                return
            with st.form(f"edit_finding_{selected['finding_id']}"):
                c1, c2, c3 = st.columns(3)
                severity = c1.selectbox("Severity", FINDING_SEVERITIES, index=option_index(FINDING_SEVERITIES, selected.get("severity")), disabled=not governance_editor)
                control_area = c2.selectbox("Control area", CONTROL_AREAS, index=option_index(CONTROL_AREAS, selected.get("control_area")), disabled=not governance_editor)
                status = c3.selectbox("Status", ["Open", "In Progress", "Closure Requested", "Closed", "Cancelled"], index=option_index(["Open", "In Progress", "Closure Requested", "Closed", "Cancelled"], selected.get("status")))
                requirement = st.text_input("Requirement", value=selected.get("requirement") or "", disabled=not governance_editor)
                description = st.text_area("Finding description", value=selected.get("finding_description") or "", disabled=not governance_editor)
                remediation = st.text_area("Remediation required / owner response", value=selected.get("remediation_required") or "", disabled=not (governance_editor or owner_editor))
                c4, c5 = st.columns(2)
                users = user_select_options(include_blank=True)
                if selected.get("assigned_to") and selected.get("assigned_to") not in users:
                    users.append(selected.get("assigned_to"))
                assigned_to = c4.selectbox("Assigned to", users, index=option_index(users, selected.get("assigned_to"), 0), disabled=not governance_editor)
                due = c5.date_input("Due date", value=_date_value(selected.get("due_date")), disabled=not governance_editor)
                closure_comments = st.text_area("Closure / validation comments", value=selected.get("closure_comments") or "")
                if st.form_submit_button("Save selected finding"):
                    if status == "Closed" and not governance_editor:
                        st.error("Closure validation is restricted to Data Validation, GCC, or Administrator roles.")
                    else:
                        try:
                            svc.update_finding_full(
                                int(selected["finding_id"]),
                                {
                                    "severity": severity,
                                    "requirement": requirement,
                                    "control_area": control_area,
                                    "finding_description": description,
                                    "remediation_required": remediation,
                                    "assigned_to": assigned_to or None,
                                    "due_date": due.isoformat() if due else None,
                                    "status": status,
                                    "closure_comments": closure_comments,
                                },
                                username,
                            )
                            st.success("Finding updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))


def page_exceptions() -> None:
    st.title("Exceptions")
    username, role = current_user()
    exceptions = svc.get_exceptions(open_only=False)
    safe_df(exceptions, height=340)
    delete_record_panel("Exception", exceptions, "exception_id", ["reference_id", "approval_status", "status"], key="exceptions_exception")
    if svc.is_read_only(role):
        return
    tabs = st.tabs(["Create exception", "Edit selected exception", "Approve / reject"])
    with tabs[0]:
        euc = euc_selector("Exception EUC")
        if euc and (svc.can_edit_euc(role, username, euc) or role in {svc.GCC_ROLE, svc.ADMIN_ROLE}):
            with st.form("create_exception"):
                gap = st.text_area("Control gap *")
                root = st.text_area("Root cause")
                comp = st.text_area("Compensating controls")
                residual = st.selectbox("Residual risk", RISK_LEVELS, index=option_index(RISK_LEVELS, euc.get("residual_risk") if euc else "Medium"))
                remediation = st.text_area("Remediation plan")
                target = st.date_input("Target date", value=date.today() + timedelta(days=60))
                expiry = st.date_input("Expiry date", value=date.today() + timedelta(days=90))
                if st.form_submit_button("Create exception"):
                    if not gap:
                        st.error("Control gap is required.")
                    else:
                        svc.create_exception({"euc_id": euc["euc_id"], "control_gap": gap, "root_cause": root, "compensating_controls": comp, "residual_risk": residual, "remediation_plan": remediation, "target_date": target.isoformat(), "expiry_date": expiry.isoformat(), "approval_status": "Pending", "status": "Open"}, username)
                        st.success("Exception created and approval task assigned.")
                        rerun()
        else:
            st.info("Select an EUC for which you have exception creation access.")
    with tabs[1]:
        if exceptions.empty:
            st.info("No exceptions available.")
        else:
            ex_map = {f"{int(row['exception_id'])} — {row['reference_id']} — {row['approval_status']} — {row['status']}": int(row["exception_id"]) for _, row in exceptions.iterrows()}
            chosen = st.selectbox("Exception to edit", list(ex_map.keys()))
            selected = exceptions[exceptions["exception_id"].astype(int) == int(ex_map[chosen])].iloc[0].to_dict()
            euc = svc.get_euc(int(selected["euc_id"]))
            governance_editor = role in {svc.GCC_ROLE, svc.ADMIN_ROLE}
            owner_editor = svc.can_edit_euc(role, username, euc)
            approver_editor = svc.can_approve(role)
            if not (governance_editor or owner_editor or approver_editor):
                st.info("You can view this exception but cannot update it in the current role.")
            else:
                with st.form(f"edit_exception_{selected['exception_id']}"):
                    gap = st.text_area("Control gap", value=selected.get("control_gap") or "", disabled=not (governance_editor or owner_editor))
                    root = st.text_area("Root cause", value=selected.get("root_cause") or "", disabled=not (governance_editor or owner_editor))
                    comp = st.text_area("Compensating controls", value=selected.get("compensating_controls") or "", disabled=not (governance_editor or owner_editor))
                    remediation = st.text_area("Remediation plan", value=selected.get("remediation_plan") or "", disabled=not (governance_editor or owner_editor))
                    c1, c2, c3 = st.columns(3)
                    residual = c1.selectbox("Residual risk", RISK_LEVELS, index=option_index(RISK_LEVELS, selected.get("residual_risk")), disabled=not governance_editor)
                    target = c2.date_input("Target date", value=_date_value(selected.get("target_date")), disabled=not (governance_editor or owner_editor))
                    expiry = c3.date_input("Expiry date", value=_date_value(selected.get("expiry_date")), disabled=not (governance_editor or approver_editor))
                    c4, c5, c6 = st.columns(3)
                    approval_status = c4.selectbox("Approval status", APPROVAL_STATUSES, index=option_index(APPROVAL_STATUSES, selected.get("approval_status")), disabled=not approver_editor)
                    status_options = ["Open", "Approved", "Rejected", "Closure Requested", "Closed", "Withdrawn", "Expired"]
                    status = c5.selectbox("Exception status", status_options, index=option_index(status_options, selected.get("status")), disabled=not (governance_editor or approver_editor or owner_editor))
                    evidence_id = c6.number_input("Closure evidence document ID", min_value=0, value=int(selected.get("closure_evidence_document_id") or 0), step=1)
                    if st.form_submit_button("Save selected exception"):
                        try:
                            svc.update_exception_full(
                                int(selected["exception_id"]),
                                {
                                    "control_gap": gap,
                                    "root_cause": root,
                                    "compensating_controls": comp,
                                    "residual_risk": residual,
                                    "remediation_plan": remediation,
                                    "target_date": target.isoformat() if target else None,
                                    "expiry_date": expiry.isoformat() if expiry else None,
                                    "approval_status": approval_status,
                                    "approved_by": username if approval_status in {"Approved", "Rejected"} else selected.get("approved_by"),
                                    "status": status,
                                    "closure_evidence_document_id": int(evidence_id) or None,
                                },
                                username,
                            )
                            st.success("Exception updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[2]:
        if not svc.can_approve(role):
            st.info("Exception approval is restricted to Approver / Head of Unit and Administrator roles.")
        elif exceptions.empty:
            st.info("No exceptions available.")
        else:
            ex_map = {f"{row['exception_id']} — {row['reference_id']} — {row['approval_status']}": int(row["exception_id"]) for _, row in exceptions.iterrows()}
            chosen = st.selectbox("Exception", list(ex_map.keys()))
            decision = st.selectbox("Decision", ["Approved", "Rejected"])
            if st.button("Record approval decision"):
                svc.approve_exception(ex_map[chosen], decision, username)
                st.success("Approval decision recorded.")
                rerun()


def page_incidents() -> None:
    st.title("Incidents & Near Misses")
    username, role = current_user()
    incidents = svc.get_incidents(open_only=False)
    safe_df(incidents, height=340)
    delete_record_panel("Incident", incidents, "incident_id", ["reference_id", "incident_date", "status"], key="incidents_incident")
    if svc.is_read_only(role):
        return
    tabs = st.tabs(["Create incident", "Edit selected incident"])
    with tabs[0]:
        euc = euc_selector("Incident EUC")
        if not euc:
            return
        if not svc.can_edit_euc(role, username, euc) and role not in {svc.GCC_ROLE, svc.ADMIN_ROLE}:
            st.info("Incident creation is available to EUC owners/delegates and governance roles.")
        else:
            with st.form("create_incident"):
                affected = st.text_area("Affected outputs")
                incident_date = st.date_input("Incident date", value=date.today())
                impact = st.text_area("Impact summary")
                containment = st.text_input("Containment status")
                correction = st.text_input("Correction status")
                rca = st.text_input("RCA status")
                remediation = st.text_area("Remediation actions")
                status = st.selectbox("Status", INCIDENT_STATUSES)
                if st.form_submit_button("Create incident"):
                    svc.create_incident({"euc_id": euc["euc_id"], "affected_outputs": affected, "incident_date": incident_date.isoformat(), "impact_summary": impact, "containment_status": containment, "correction_status": correction, "rca_status": rca, "remediation_actions": remediation, "status": status}, username)
                    st.success("Incident recorded. Reassessment and documentation refresh tasks were generated.")
                    rerun()
    with tabs[1]:
        if incidents.empty:
            st.info("No incidents available.")
        else:
            inc_map = {f"{int(row['incident_id'])} — {row['reference_id']} — {row['incident_date']} — {row['status']}": int(row["incident_id"]) for _, row in incidents.iterrows()}
            chosen = st.selectbox("Incident to edit", list(inc_map.keys()))
            selected = incidents[incidents["incident_id"].astype(int) == int(inc_map[chosen])].iloc[0].to_dict()
            euc = svc.get_euc(int(selected["euc_id"]))
            if not can_edit_operational_record(role, username, euc, {svc.GCC_ROLE, svc.ADMIN_ROLE}):
                st.info("You can view this incident but cannot update it in the current role.")
            else:
                with st.form(f"edit_incident_{selected['incident_id']}"):
                    affected = st.text_area("Affected outputs", value=selected.get("affected_outputs") or "")
                    incident_date = st.date_input("Incident date", value=_date_value(selected.get("incident_date")))
                    impact = st.text_area("Impact summary", value=selected.get("impact_summary") or "")
                    c1, c2, c3 = st.columns(3)
                    containment = c1.text_input("Containment status", value=selected.get("containment_status") or "")
                    correction = c2.text_input("Correction status", value=selected.get("correction_status") or "")
                    rca = c3.text_input("RCA status", value=selected.get("rca_status") or "")
                    remediation = st.text_area("Remediation actions", value=selected.get("remediation_actions") or "")
                    status = st.selectbox("Status", INCIDENT_STATUSES, index=option_index(INCIDENT_STATUSES, selected.get("status")))
                    if st.form_submit_button("Save selected incident"):
                        svc.update_incident(int(selected["incident_id"]), {"affected_outputs": affected, "incident_date": incident_date.isoformat(), "impact_summary": impact, "containment_status": containment, "correction_status": correction, "rca_status": rca, "remediation_actions": remediation, "status": status}, username)
                        st.success("Incident updated.")
                        rerun()


def page_material_changes() -> None:
    st.title("Material Changes & Reassessments")
    username, role = current_user()
    changes = svc.get_material_changes()
    safe_df(changes, height=330)
    delete_record_panel("Material Change", changes, "change_id", ["reference_id", "change_type", "status"], key="changes_change")
    if svc.is_read_only(role):
        return
    tabs = st.tabs(["Record material change", "Edit selected material change"])
    with tabs[0]:
        euc = euc_selector("Changed EUC")
        if not euc:
            return
        if not svc.can_edit_euc(role, username, euc) and role not in {svc.GCC_ROLE, svc.ADMIN_ROLE}:
            st.info("Material change creation is available to EUC owners/delegates and governance roles.")
        else:
            with st.form("material_change"):
                change_type = st.selectbox("Change type", CHANGE_TYPES)
                description = st.text_area("Description *")
                impact = st.text_area("Impact assessment")
                reassessment = st.checkbox("Reassessment required", value=True)
                doc_refresh = st.checkbox("Documentation refresh required", value=True)
                status = st.selectbox("Status", ["Open", "In Assessment", "Awaiting Reassessment", "Closed"])
                if st.form_submit_button("Record material change"):
                    if not description:
                        st.error("Description is required.")
                    else:
                        svc.create_material_change({"euc_id": euc["euc_id"], "change_type": change_type, "description": description, "impact_assessment": impact, "reassessment_required": reassessment, "documentation_refresh_required": doc_refresh, "status": status}, username)
                        st.success("Material change recorded and follow-up tasks generated as applicable.")
                        rerun()
    with tabs[1]:
        if changes.empty:
            st.info("No material changes available.")
        else:
            ch_map = {f"{int(row['change_id'])} — {row['reference_id']} — {row['change_type']} — {row['status']}": int(row["change_id"]) for _, row in changes.iterrows()}
            chosen = st.selectbox("Material change to edit", list(ch_map.keys()))
            selected = changes[changes["change_id"].astype(int) == int(ch_map[chosen])].iloc[0].to_dict()
            euc = svc.get_euc(int(selected["euc_id"]))
            if not can_edit_operational_record(role, username, euc, {svc.GCC_ROLE, svc.ADMIN_ROLE}):
                st.info("You can view this material change but cannot update it in the current role.")
            else:
                with st.form(f"edit_change_{selected['change_id']}"):
                    c1, c2, c3 = st.columns(3)
                    change_type = c1.selectbox("Change type", CHANGE_TYPES, index=option_index(CHANGE_TYPES, selected.get("change_type")))
                    reassessment = c2.checkbox("Reassessment required", value=bool(int(selected.get("reassessment_required") or 0)))
                    doc_refresh = c3.checkbox("Documentation refresh required", value=bool(int(selected.get("documentation_refresh_required") or 0)))
                    description = st.text_area("Description", value=selected.get("description") or "")
                    impact = st.text_area("Impact assessment", value=selected.get("impact_assessment") or "")
                    status_options = ["Open", "In Assessment", "Awaiting Reassessment", "Closed"]
                    status = st.selectbox("Status", status_options, index=option_index(status_options, selected.get("status")))
                    if st.form_submit_button("Save selected material change"):
                        try:
                            svc.update_material_change(int(selected["change_id"]), {"change_type": change_type, "description": description, "impact_assessment": impact, "reassessment_required": reassessment, "documentation_refresh_required": doc_refresh, "status": status}, username)
                            st.success("Material change updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))


def page_lifecycle() -> None:
    st.title("Industrialization & Decommissioning")
    username, role = current_user()
    df = svc.all_eucs(role, username)
    candidates = df[df["lifecycle_status"].isin(["Industrialization Candidate", "Decommissioned", "Archived"])] if not df.empty else df
    st.subheader("Current lifecycle candidates")
    safe_df(candidates[[c for c in ["reference_id", "name", "owner", "residual_risk", "lifecycle_status", "industrialization_rationale", "decommissioning_rationale"] if c in candidates.columns]] if not candidates.empty else candidates)
    if svc.is_read_only(role):
        return
    euc = euc_selector("Lifecycle EUC")
    if not euc:
        return
    if not svc.can_edit_euc(role, username, euc) and role not in {svc.GCC_ROLE, svc.ADMIN_ROLE}:
        st.info("Lifecycle changes are available to EUC owners/delegates and governance roles.")
        return
    tabs = st.tabs(["Edit lifecycle fields", "Mark industrialization candidate", "Controlled decommissioning"])
    with tabs[0]:
        governance_editor = role in {svc.GCC_ROLE, svc.ADMIN_ROLE}
        with st.form("edit_lifecycle_fields"):
            lifecycle = st.selectbox("Lifecycle status", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, euc.get("lifecycle_status")), disabled=not governance_editor)
            overall = st.selectbox("Overall status", OVERALL_STATUSES, index=option_index(OVERALL_STATUSES, euc.get("overall_status")), disabled=not governance_editor)
            industrialization_rationale = st.text_area("Industrialization rationale", value=euc.get("industrialization_rationale") or "")
            decommissioning_rationale = st.text_area("Decommissioning rationale", value=euc.get("decommissioning_rationale") or "")
            if st.form_submit_button("Save lifecycle fields"):
                payload = dict(euc)
                payload.update({"lifecycle_status": lifecycle, "overall_status": overall, "industrialization_rationale": industrialization_rationale, "decommissioning_rationale": decommissioning_rationale})
                svc.update_euc(euc["euc_id"], payload, username)
                st.success("Lifecycle fields updated.")
                rerun()
    with tabs[1]:
        with st.form("industrialization"):
            rationale = st.text_area("Industrialization rationale", value=euc.get("industrialization_rationale") or "")
            if st.form_submit_button("Mark as industrialization candidate"):
                payload = dict(euc)
                payload["industrialization_rationale"] = rationale
                payload["lifecycle_status"] = "Industrialization Candidate"
                payload["overall_status"] = "Industrialization candidate"
                svc.update_euc(euc["euc_id"], payload, username)
                svc.update_euc_status(euc["euc_id"], "Industrialization Candidate", username, "Industrialization candidate")
                st.success("EUC marked as industrialization candidate.")
                rerun()
    with tabs[2]:
        st.warning("Controlled decommissioning closes open obligations as cancelled/closed and retains final evidence records.")
        with st.form("decommission"):
            rationale = st.text_area("Decommissioning rationale", value=euc.get("decommissioning_rationale") or "")
            confirm = st.checkbox("I confirm final evidence is retained or will be uploaded before archival.")
            if st.form_submit_button("Decommission EUC"):
                if not confirm:
                    st.error("Confirmation is required before controlled decommissioning.")
                else:
                    payload = dict(euc)
                    payload["decommissioning_rationale"] = rationale
                    svc.update_euc(euc["euc_id"], payload, username)
                    result = svc.close_open_obligations_for_decommissioning(euc["euc_id"], username)
                    st.success(f"EUC decommissioned. Tasks closed/cancelled: {result['tasks_closed']}; findings closed: {result['findings_closed']}.")
                    rerun()


def page_reports() -> None:
    st.title("Reports & KPIs")
    df = svc.all_eucs()
    c1, c2, c3, c4 = st.columns(4)
    owner = c1.selectbox("Owner", ["All"] + sorted(df["owner"].dropna().unique().tolist()) if not df.empty else ["All"])
    unit = c2.selectbox("Business unit", ["All"] + sorted(df["business_unit"].dropna().unique().tolist()) if not df.empty else ["All"])
    risk = c3.selectbox("Risk level", ["All"] + RISK_LEVELS)
    status = c4.selectbox("Status", ["All"] + LIFECYCLE_STATUSES)
    c5, c6, c7 = st.columns(3)
    due_before_enabled = c5.checkbox("Filter by task due date")
    due_before = c6.date_input("Due on/before", value=date.today() + timedelta(days=30), disabled=not due_before_enabled)
    output_mapping = c7.text_input("Output mapping contains")
    control_area = st.selectbox("Control area", ["All"] + CONTROL_AREAS)
    report = svc.report_table({"owner": owner, "business_unit": unit, "risk_level": risk, "status": status, "due_before": due_before.isoformat() if due_before_enabled else None, "output_mapping": output_mapping, "control_area": control_area})
    safe_df(report, height=460)
    csv_download(report, "euc_governance_report.csv")


def page_admin() -> None:
    st.title("Admin Configuration")
    username, role = current_user()
    if not svc.can_configure(role):
        st.warning("Admin Configuration is restricted to Group IT Governance Administrator.")
        return
    refs = svc.load_reference_data()
    tabs = st.tabs(["Reference data", "Required artifact rules", "User directory", "Due-date rules", "Seed/reset demo"])

    with tabs[0]:
        category_options = ["document_type", "lifecycle_status", "risk_level", "control_area", "cacrt_dimension"]
        category = st.selectbox("Category", category_options)
        ref_df = svc.reference_data_table(category)
        safe_df(ref_df, height=300)
        delete_record_panel("Reference Data", ref_df, "ref_id", ["category", "value"], key="admin_reference_data")
        ref_tabs = st.tabs(["Add value", "Edit selected value"])
        with ref_tabs[0]:
            with st.form("add_ref"):
                value = st.text_input("New reference value")
                comments = st.text_area("Maker-checker comments")
                if st.form_submit_button("Add reference value"):
                    if value.strip():
                        svc.upsert_reference_value(category, value.strip(), username, comments)
                        st.success("Reference value added.")
                        rerun()
                    else:
                        st.error("Value is required.")
        with ref_tabs[1]:
            if ref_df.empty:
                st.info("No reference data values exist for this category.")
            else:
                ref_map = {f"{int(row['ref_id'])} — {row['category']} — {row['value']}": int(row["ref_id"]) for _, row in ref_df.iterrows()}
                chosen = st.selectbox("Reference row", list(ref_map.keys()))
                selected = ref_df[ref_df["ref_id"].astype(int) == int(ref_map[chosen])].iloc[0].to_dict()
                with st.form(f"edit_ref_{selected['ref_id']}"):
                    edit_category = st.selectbox("Category", category_options, index=option_index(category_options, selected.get("category")))
                    value = st.text_input("Value", value=selected.get("value") or "")
                    active = st.checkbox("Active", value=bool(int(selected.get("active_flag") or 0)))
                    approval_status = st.selectbox("Approval status", APPROVAL_STATUSES, index=option_index(APPROVAL_STATUSES, selected.get("approval_status")))
                    comments = st.text_area("Maker-checker comments", value=selected.get("maker_checker_comments") or "")
                    if st.form_submit_button("Save selected reference value"):
                        try:
                            svc.update_reference_value(int(selected["ref_id"]), {"category": edit_category, "value": value.strip(), "active_flag": active, "maker_checker_comments": comments, "approval_status": approval_status, "approved_by": username if approval_status == "Approved" else selected.get("approved_by")}, username)
                            st.success("Reference value updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))

    with tabs[1]:
        rules_df = svc.required_rules_table()
        safe_df(rules_df, height=320)
        delete_record_panel("Required Artifact Rule", rules_df, "rule_id", ["risk_level", "required_document_type"], key="admin_rule")
        rule_tabs = st.tabs(["Create rule", "Edit selected rule"])
        with rule_tabs[0]:
            with st.form("add_rule"):
                c1, c2, c3 = st.columns(3)
                risk = c1.selectbox("Risk level", RISK_LEVELS)
                lifecycle = c2.selectbox("Lifecycle stage", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, "Active"))
                doc_type = c3.selectbox("Required document type", DOCUMENT_TYPES)
                control = c1.selectbox("Control area", CONTROL_AREAS)
                cacrt = c2.selectbox("CACRT dimension", CACRT_DIMENSIONS)
                mandatory = c3.checkbox("Mandatory", value=True)
                comments = st.text_area("Maker-checker comments")
                if st.form_submit_button("Create required artifact rule"):
                    svc.upsert_required_rule({"risk_level": risk, "lifecycle_stage": lifecycle, "required_document_type": doc_type, "control_area": control, "cacrt_dimension": cacrt, "mandatory_flag": mandatory, "maker_checker_comments": comments}, username)
                    st.success("Rule created.")
                    rerun()
        with rule_tabs[1]:
            if rules_df.empty:
                st.info("No rules exist.")
            else:
                rule_map = {f"{int(row['rule_id'])} — {row['risk_level']} — {row['required_document_type']}": int(row["rule_id"]) for _, row in rules_df.iterrows()}
                chosen = st.selectbox("Required artifact rule", list(rule_map.keys()))
                selected = rules_df[rules_df["rule_id"].astype(int) == int(rule_map[chosen])].iloc[0].to_dict()
                with st.form(f"edit_rule_{selected['rule_id']}"):
                    c1, c2, c3 = st.columns(3)
                    risk = c1.selectbox("Risk level", RISK_LEVELS, index=option_index(RISK_LEVELS, selected.get("risk_level")))
                    lifecycle = c2.selectbox("Lifecycle stage", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, selected.get("lifecycle_stage")))
                    doc_type = c3.selectbox("Required document type", DOCUMENT_TYPES, index=option_index(DOCUMENT_TYPES, selected.get("required_document_type")))
                    control = c1.selectbox("Control area", CONTROL_AREAS, index=option_index(CONTROL_AREAS, selected.get("control_area")))
                    cacrt = c2.selectbox("CACRT dimension", CACRT_DIMENSIONS, index=option_index(CACRT_DIMENSIONS, selected.get("cacrt_dimension")))
                    mandatory = c3.checkbox("Mandatory", value=bool(int(selected.get("mandatory_flag") or 0)))
                    approval_status = st.selectbox("Approval status", APPROVAL_STATUSES, index=option_index(APPROVAL_STATUSES, selected.get("approval_status")))
                    comments = st.text_area("Maker-checker comments", value=selected.get("maker_checker_comments") or "")
                    if st.form_submit_button("Save selected rule"):
                        svc.update_required_rule(int(selected["rule_id"]), {"risk_level": risk, "lifecycle_stage": lifecycle, "required_document_type": doc_type, "control_area": control, "cacrt_dimension": cacrt, "mandatory_flag": mandatory, "maker_checker_comments": comments, "approval_status": approval_status, "approved_by": username if approval_status == "Approved" else selected.get("approved_by")}, username)
                        st.success("Required artifact rule updated.")
                        rerun()

    with tabs[2]:
        users = svc.user_directory(active_only=False)
        st.caption("This local directory maps task assignees to names and emails. It is intentionally separate from SSO for the MVP.")

        selected_user_id = st.session_state.get("admin_selected_user_id")
        if users is not None and not users.empty:
            st.caption("Select one user row in the table to load it for editing below.")
            event = st.dataframe(
                users,
                use_container_width=True,
                hide_index=True,
                height=320,
                selection_mode="single-row",
                on_select="rerun",
                key="admin_user_directory_table",
            )
            try:
                selected_rows = list(event.selection.rows)
            except Exception:
                selected_rows = []
            if selected_rows:
                selected_user_id = int(users.iloc[selected_rows[0]]["user_id"])
                st.session_state["admin_selected_user_id"] = selected_user_id

            if selected_user_id and selected_user_id not in set(users["user_id"].astype(int).tolist()):
                st.session_state.pop("admin_selected_user_id", None)
                selected_user_id = None
        else:
            st.info("No users exist yet. Create the first user profile below.")

        delete_record_panel("User Profile", users, "user_id", ["username", "email", "role"], key="admin_user_profile")

        selected_user: dict[str, Any] | None = None
        if users is not None and not users.empty and selected_user_id:
            match = users[users["user_id"].astype(int) == int(selected_user_id)]
            if not match.empty:
                selected_user = match.iloc[0].to_dict()
                st.info(f"Editing selected user: {selected_user.get('username')} · {selected_user.get('email')}")

        c_new, c_clear = st.columns([1, 3])
        if c_new.button("Create new user instead", disabled=selected_user is None):
            st.session_state.pop("admin_selected_user_id", None)
            rerun()
        if c_clear.button("Clear table selection", disabled=selected_user is None):
            st.session_state.pop("admin_selected_user_id", None)
            rerun()

        form_key = f"user_profile_form_{selected_user_id or 'new'}"
        with st.form(form_key):
            c1, c2 = st.columns(2)
            default_username = str(selected_user.get("username", "")) if selected_user else ""
            default_full_name = str(selected_user.get("full_name", "")) if selected_user else ""
            default_email = str(selected_user.get("email", "")) if selected_user else ""
            default_role = str(selected_user.get("role", ROLES[0])) if selected_user else ROLES[0]
            default_active = bool(int(selected_user.get("active_flag", 1))) if selected_user else True

            new_username = c1.text_input("Username *", value=default_username, placeholder="Firstname.Lastname")
            full_name = c2.text_input("Full name *", value=default_full_name)
            email = c1.text_input("Email *", value=default_email, placeholder="name@eurobank.gr")
            user_role = c2.selectbox("Role *", ROLES, index=option_index(ROLES, default_role))
            active_flag = st.checkbox("Active", value=default_active)
            submit_label = "Save selected user profile" if selected_user else "Create user profile"
            if st.form_submit_button(submit_label):
                try:
                    payload = {
                        "username": new_username.strip(),
                        "full_name": full_name.strip(),
                        "email": email.strip(),
                        "role": user_role,
                        "active_flag": active_flag,
                    }
                    if selected_user:
                        svc.update_user_profile(int(selected_user["user_id"]), payload, username)
                    else:
                        svc.upsert_user_profile(payload, username)
                    st.success("User profile saved.")
                    rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tabs[3]:
        due_rules_df = svc.due_date_rules_table()
        safe_df(due_rules_df, height=360)
        delete_record_panel("Due-date Rule", due_rules_df, "rule_id", ["task_type", "risk_level", "due_days"], key="admin_due_rule")
        due_tabs = st.tabs(["Create due-date rule", "Edit selected due-date rule"])
        with due_tabs[0]:
            with st.form("create_due_rule"):
                c1, c2, c3 = st.columns(3)
                task_type = c1.selectbox("Task type", TASK_TYPES)
                risk_level = c2.selectbox("Risk level", ["Any"] + RISK_LEVELS)
                due_days = c3.number_input("Due days", min_value=0, value=10, step=1)
                active = c1.checkbox("Active", value=True)
                approval_status = c2.selectbox("Approval status", APPROVAL_STATUSES, index=option_index(APPROVAL_STATUSES, "Approved"))
                comments = st.text_area("Maker-checker comments")
                if st.form_submit_button("Create due-date rule"):
                    try:
                        svc.create_due_date_rule({"task_type": task_type, "risk_level": risk_level, "due_days": int(due_days), "active_flag": active, "maker_checker_comments": comments, "approval_status": approval_status}, username)
                        st.success("Due-date rule created.")
                        rerun()
                    except Exception as exc:
                        st.error(f"Could not create due-date rule: {exc}")
        with due_tabs[1]:
            if due_rules_df.empty:
                st.info("No due-date rules exist.")
            else:
                due_map = {f"{int(row['rule_id'])} — {row['task_type']} — {row.get('risk_level') or 'Any'} — {row['due_days']} days": int(row["rule_id"]) for _, row in due_rules_df.iterrows()}
                chosen = st.selectbox("Due-date rule", list(due_map.keys()))
                selected = due_rules_df[due_rules_df["rule_id"].astype(int) == int(due_map[chosen])].iloc[0].to_dict()
                with st.form(f"edit_due_rule_{selected['rule_id']}"):
                    c1, c2, c3 = st.columns(3)
                    task_type = c1.selectbox("Task type", TASK_TYPES, index=option_index(TASK_TYPES, selected.get("task_type")))
                    risk_options = ["Any"] + RISK_LEVELS
                    risk_level = c2.selectbox("Risk level", risk_options, index=option_index(risk_options, selected.get("risk_level") or "Any"))
                    due_days = c3.number_input("Due days", min_value=0, value=int(selected.get("due_days") or 0), step=1)
                    active = c1.checkbox("Active", value=bool(int(selected.get("active_flag") or 0)))
                    approval_status = c2.selectbox("Approval status", APPROVAL_STATUSES, index=option_index(APPROVAL_STATUSES, selected.get("approval_status")))
                    comments = st.text_area("Maker-checker comments", value=selected.get("maker_checker_comments") or "")
                    if st.form_submit_button("Save selected due-date rule"):
                        try:
                            svc.update_due_date_rule(int(selected["rule_id"]), {"task_type": task_type, "risk_level": risk_level, "due_days": int(due_days), "active_flag": active, "maker_checker_comments": comments, "approval_status": approval_status, "approved_by": username if approval_status == "Approved" else selected.get("approved_by")}, username)
                            st.success("Due-date rule updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[4]:
        st.warning("The app auto-seeds an empty local database for demo readiness. Use the command-line seed script for controlled resets.")
        if st.button("Run seed data loader", type="secondary"):
            seed_database(force=False)
            st.success("Seed loader executed. Existing records were not overwritten.")


def page_audit() -> None:
    st.title("Audit Trail")
    username, role = current_user()
    st.caption("Audit records are immutable from the UI.")
    c1, c2, c3, c4, c5 = st.columns(5)
    entity_type = c1.text_input("Entity type")
    entity_id = c2.text_input("Entity ID")
    performed_by = c3.text_input("User")
    from_date_enabled = c4.checkbox("From date")
    to_date_enabled = c5.checkbox("To date")
    c6, c7 = st.columns(2)
    from_date = c6.date_input("From", value=date.today() - timedelta(days=30), disabled=not from_date_enabled)
    to_date = c7.date_input("To", value=date.today(), disabled=not to_date_enabled)
    audit = svc.audit_trail({"entity_type": entity_type or None, "entity_id": entity_id or None, "performed_by": performed_by or None, "from_date": from_date.isoformat() if from_date_enabled else None, "to_date": to_date.isoformat() if to_date_enabled else None})
    safe_df(audit, height=520)
    csv_download(audit, "audit_trail.csv")


def route(page: str) -> None:
    routes = {
        "Home / Dashboard": page_dashboard,
        "EUC Inventory": page_inventory,
        "Register New EUC": page_register,
        "EUC Detail View": page_detail,
        "Components / Assets": page_components,
        "Risk Assessment": page_risk_assessment,
        "Documents & Evidence Pack": page_documents,
        "Required Artifact Checklist": page_checklist,
        "Tasks & Remediation": page_tasks,
        "Data Validation Review Queue": page_dvu_queue,
        "GCC Monitoring View": page_gcc,
        "Findings & Challenge Management": page_findings,
        "Exceptions": page_exceptions,
        "Incidents & Near Misses": page_incidents,
        "Material Changes & Reassessments": page_material_changes,
        "Industrialization & Decommissioning": page_lifecycle,
        "Reports & KPIs": page_reports,
        "Admin Configuration": page_admin,
        "Audit Trail": page_audit,
    }
    routes[page]()


def main() -> None:
    bootstrap()
    apply_query_params()
    if "role" not in st.session_state:
        st.session_state["role"] = ROLES[0]
    if "username" not in st.session_state:
        st.session_state["username"] = svc.username_options_for_role(st.session_state["role"])[0]
    show_login()
    page = show_sidebar()
    route(page)


if __name__ == "__main__":
    main()
