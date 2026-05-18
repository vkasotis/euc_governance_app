"""Streamlit UI for the End-to-End EUC Governance Monitoring App."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

import services as svc
from db import DATABASE_FILE, init_db, table_count
from schema import (
    APP_TITLE,
    BANK_NAME,
    APPROVAL_STATUSES,
    CACRT_DIMENSIONS,
    CHANGE_TYPES,
    CONTROL_AREAS,
    DOCUMENT_STATUSES,
    DOCUMENT_TYPES,
    FINDING_SEVERITIES,
    FREQUENCIES,
    INCIDENT_STATUSES,
    LIFECYCLE_STATUSES,
    OVERALL_STATUSES,
    PRIORITIES,
    REVIEW_OUTCOMES,
    REVIEW_TYPES,
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
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def csv_download(df: pd.DataFrame, file_name: str, label: str = "Download CSV") -> None:
    if df is not None and not df.empty:
        st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=file_name, mime="text/csv")


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
    page = st.sidebar.radio("Navigation", NAVIGATION, index=0)
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
    show_cols = ["euc_id", "reference_id", "name", "owner", "business_unit", "technology_type", "residual_risk", "lifecycle_status", "documentation_completeness_status", "spof_indicator", "next_review_date"]
    safe_df(filtered[show_cols], height=500)
    csv_download(filtered[show_cols], "euc_inventory.csv")
    if not filtered.empty:
        selected_ref = st.selectbox("Open EUC in detail view", filtered["reference_id"].tolist())
        if st.button("Set selected EUC"):
            row = filtered[filtered["reference_id"] == selected_ref].iloc[0]
            st.session_state["selected_euc_id"] = int(row["euc_id"])
            st.success(f"Selected {selected_ref}. Use EUC Detail View to continue.")


def page_register() -> None:
    st.title("Register New EUC")
    username, role = current_user()
    if role not in {svc.OWNER_ROLE, svc.ADMIN_ROLE, svc.CONTRIBUTOR_ROLE}:
        st.warning("Registration is restricted to EUC Owners, Contributors, and Administrators in this MVP.")
        return
    if not require_write_access():
        return

    with st.form("register_euc"):
        st.subheader("Core EUC information")
        c1, c2 = st.columns(2)
        name = c1.text_input("EUC name *")
        owner = c2.text_input("Owner *", value=username if role == svc.OWNER_ROLE else "")
        owner_delegate = c1.text_input("Owner delegate / contributor")
        business_unit = c2.text_input("Business unit *", value="Risk Management")
        technology_type = c1.selectbox("Technology type *", TECHNOLOGY_TYPES)
        storage_location = c2.text_input("Storage location *", value="//eurobank/euc/")
        description = st.text_area("Description")
        purpose = st.text_area("Purpose")

        st.subheader("Mapping and operating context")
        c3, c4, c5 = st.columns(3)
        frequency = c3.selectbox("Frequency", FREQUENCIES)
        schedule = c4.text_input("Execution schedule")
        cut_off = c5.text_input("Cut-off")
        business_context = st.text_area("Business context")
        bcbs_mapping = st.text_area("BCBS 239 output mapping *", help="At least one in-scope output is required.")
        cde_linkage = st.text_area("CDE linkage (optional)")
        inputs = st.text_area("Inputs")
        outputs = st.text_area("Outputs")
        recipients = st.text_area("Recipients")
        dependencies = st.text_area("Dependencies")
        spof = st.radio("SPOF indicator", ["No", "Yes"], horizontal=True)
        mapping_na_justification = st.text_area("Not Applicable justification", help="Required if any mapping field is 'Not Applicable'.")
        lifecycle_status = st.selectbox("Initial lifecycle status", ["Draft", "Submitted", "Registered"], index=2)
        next_review_date = st.date_input("Next review date", value=date.today() + timedelta(days=90))
        submitted = st.form_submit_button("Register EUC")

    if submitted:
        try:
            duplicates = svc.detect_duplicates(name, owner, business_unit, storage_location)
            euc_id = svc.create_euc(
                {
                    "name": name,
                    "description": description,
                    "purpose": purpose,
                    "owner": owner,
                    "owner_delegate": owner_delegate,
                    "business_unit": business_unit,
                    "technology_type": technology_type,
                    "storage_location": storage_location,
                    "frequency": frequency,
                    "schedule": schedule,
                    "cut_off": cut_off,
                    "business_context": business_context,
                    "bcbs239_output_mapping": bcbs_mapping,
                    "cde_linkage": cde_linkage,
                    "inputs": inputs,
                    "outputs": outputs,
                    "recipients": recipients,
                    "dependencies": dependencies,
                    "spof_indicator": spof,
                    "lifecycle_status": lifecycle_status,
                    "overall_status": lifecycle_status,
                    "next_review_date": next_review_date.isoformat(),
                    "mapping_na_justification": mapping_na_justification,
                },
                username,
            )
            st.session_state["selected_euc_id"] = euc_id
            st.success("EUC registered and initial risk assessment/document submission tasks created.")
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

    tabs = st.tabs(["Overview", "Mapping", "Components", "Risk History", "Evidence", "Tasks", "Reviews", "Audit"])
    with tabs[0]:
        st.write(euc.get("description") or "No description recorded.")
        st.json({k: euc.get(k) for k in ["purpose", "business_unit", "technology_type", "storage_location", "frequency", "schedule", "cut_off", "spof_indicator", "next_review_date"]})
        if svc.can_edit_euc(role, username, euc):
            with st.expander("Edit EUC summary and lifecycle"):
                with st.form("edit_euc"):
                    name = st.text_input("Name", value=euc.get("name") or "")
                    owner = st.text_input("Owner", value=euc.get("owner") or "")
                    delegate = st.text_input("Owner delegate", value=euc.get("owner_delegate") or "")
                    unit = st.text_input("Business unit", value=euc.get("business_unit") or "")
                    tech = st.selectbox("Technology", TECHNOLOGY_TYPES, index=option_index(TECHNOLOGY_TYPES, euc.get("technology_type")))
                    storage = st.text_input("Storage location", value=euc.get("storage_location") or "")
                    lifecycle = st.selectbox("Lifecycle status", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, euc.get("lifecycle_status")))
                    overall = st.selectbox("Overall status", OVERALL_STATUSES, index=option_index(OVERALL_STATUSES, euc.get("overall_status")))
                    next_review = st.date_input("Next review date", value=pd.to_datetime(euc.get("next_review_date") or date.today()).date())
                    description = st.text_area("Description", value=euc.get("description") or "")
                    purpose = st.text_area("Purpose", value=euc.get("purpose") or "")
                    if st.form_submit_button("Save changes"):
                        payload = dict(euc)
                        payload.update({"name": name, "owner": owner, "owner_delegate": delegate, "business_unit": unit, "technology_type": tech, "storage_location": storage, "lifecycle_status": lifecycle, "overall_status": overall, "next_review_date": next_review.isoformat(), "description": description, "purpose": purpose})
                        try:
                            svc.update_euc(euc["euc_id"], payload, username)
                            st.success("EUC updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[1]:
        st.json({k: euc.get(k) for k in ["business_context", "bcbs239_output_mapping", "cde_linkage", "inputs", "outputs", "recipients", "dependencies", "mapping_na_justification"]})
        if svc.can_edit_euc(role, username, euc):
            with st.expander("Edit mapping fields"):
                with st.form("edit_mapping"):
                    payload = dict(euc)
                    for field in ["business_context", "bcbs239_output_mapping", "cde_linkage", "inputs", "outputs", "recipients", "dependencies", "mapping_na_justification"]:
                        payload[field] = st.text_area(field.replace("_", " ").title(), value=euc.get(field) or "")
                    if st.form_submit_button("Save mapping"):
                        try:
                            svc.update_euc(euc["euc_id"], payload, username)
                            st.success("Mapping updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[2]:
        safe_df(svc.get_components(euc["euc_id"]))
    with tabs[3]:
        safe_df(svc.get_risk_assessments(euc["euc_id"]))
    with tabs[4]:
        safe_df(svc.get_documents(euc["euc_id"]))
    with tabs[5]:
        tasks = svc.get_tasks(open_only=False)
        if not tasks.empty:
            tasks = tasks[tasks["euc_id"] == euc["euc_id"]]
        safe_df(tasks)
    with tabs[6]:
        safe_df(svc.get_reviews(euc["euc_id"]))
    with tabs[7]:
        safe_df(svc.audit_trail({"entity_type": "EUC", "entity_id": euc["euc_id"]}), height=350)


def page_components() -> None:
    st.title("Components / Assets")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return
    safe_df(svc.get_components(euc["euc_id"]), height=350)
    if not svc.can_edit_euc(role, username, euc):
        st.info("You can view components but cannot add components for this EUC in the current role.")
        return
    with st.form("add_component"):
        st.subheader("Add component")
        c1, c2 = st.columns(2)
        component_name = c1.text_input("Component name *")
        component_type = c2.selectbox("Component type *", TECHNOLOGY_TYPES)
        technology = c1.text_input("Technology", value=euc.get("technology_type") or "")
        storage_location = c2.text_input("Storage location", value=euc.get("storage_location") or "")
        criticality = c1.selectbox("Criticality", ["Low", "Medium", "High", "Critical"])
        owner = c2.text_input("Owner", value=euc.get("owner") or username)
        description = st.text_area("Description")
        if st.form_submit_button("Add component"):
            if not component_name:
                st.error("Component name is required.")
            else:
                svc.create_component({"euc_id": euc["euc_id"], "component_name": component_name, "component_type": component_type, "technology": technology, "storage_location": storage_location, "criticality": criticality, "owner": owner, "description": description}, username)
                st.success("Component added.")
                rerun()


def page_risk_assessment() -> None:
    st.title("Risk Assessment")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return
    st.info("Risk levels use the MVP rule: average score 1.0–1.9 Low, 2.0–2.9 Medium, 3.0–3.9 High, 4.0–5.0 Very High.")
    safe_df(svc.get_risk_assessments(euc["euc_id"]), height=260)
    if not svc.can_edit_euc(role, username, euc) and role not in {svc.ADMIN_ROLE, svc.GCC_ROLE}:
        st.warning("Only the EUC owner/delegate or governance roles can record assessments.")
        return
    with st.form("risk_assessment"):
        c1, c2, c3, c4, c5 = st.columns(5)
        integrity = c1.slider("Integrity / accuracy", 1, 5, 3)
        timeliness = c2.slider("Timeliness / availability", 1, 5, 3)
        complexity = c3.slider("Complexity", 1, 5, 3)
        criticality = c4.slider("Business criticality", 1, 5, 3)
        controls = c5.slider("Control effectiveness", 1, 5, 3, help="Higher means weaker controls / greater residual concern in this MVP scoring convention.")
        trigger = st.selectbox("Trigger type", ["Material change", "Incident", "Periodic review", "Manual trigger"])
        rationale = st.text_area("Rationale")
        if st.form_submit_button("Submit assessment"):
            assessment_id = svc.create_risk_assessment({"euc_id": euc["euc_id"], "assessment_date": date.today().isoformat(), "assessed_by": username, "integrity_accuracy_score": integrity, "timeliness_availability_score": timeliness, "complexity_score": complexity, "business_criticality_score": criticality, "control_effectiveness_score": controls, "trigger_type": trigger, "rationale": rationale}, username)
            st.success(f"Assessment {assessment_id} submitted and EUC risk/completeness recalculated.")
            rerun()


def page_documents() -> None:
    st.title("Documents & Evidence Pack")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return
    docs = svc.get_documents(euc["euc_id"])
    safe_df(docs, height=320)

    col_upload, col_review = st.columns(2)
    with col_upload:
        st.subheader("Upload evidence")
        if svc.can_upload_evidence(role, username, euc) and require_write_access():
            uploaded = st.file_uploader("Upload document / evidence")
            with st.form("doc_metadata"):
                document_type = st.selectbox("Document type", DOCUMENT_TYPES)
                requirement = st.text_input("Requirement", value=f"Mandatory {document_type}")
                control_area = st.selectbox("Control area", CONTROL_AREAS)
                cacrt = st.selectbox("CACRT dimension", CACRT_DIMENSIONS)
                risk_app = st.selectbox("Risk applicability", ["All", "Low", "Medium", "High", "Very High"])
                lifecycle_stage = st.selectbox("Lifecycle stage", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, euc.get("lifecycle_status")))
                version = st.text_input("Version", value="1.0")
                status = st.selectbox("Initial status", ["Submitted", "Pending"])
                comments = st.text_area("Comments")
                if st.form_submit_button("Save uploaded evidence"):
                    if uploaded is None:
                        st.error("Select a file before saving metadata.")
                    else:
                        file_name, file_path = svc.save_document_file(euc["euc_id"], uploaded.name, uploaded.getvalue())
                        doc_id = svc.create_document_record({"euc_id": euc["euc_id"], "file_name": file_name, "file_path": file_path, "document_type": document_type, "requirement": requirement, "control_area": control_area, "cacrt_dimension": cacrt, "risk_applicability": risk_app, "lifecycle_stage": lifecycle_stage, "version": version, "status": status, "comments": comments}, username)
                        st.success(f"Evidence uploaded as document {doc_id}.")
                        rerun()
        else:
            st.info("Upload is disabled for the current role/EUC relationship.")

    with col_review:
        st.subheader("Review evidence")
        if svc.can_review(role) and require_write_access() and not docs.empty:
            doc_map = {f"{row['document_id']} — {row['document_type']} — {row['status']}": int(row["document_id"]) for _, row in docs.iterrows()}
            chosen = st.selectbox("Document", list(doc_map.keys()))
            with st.form("review_doc"):
                status = st.selectbox("Review status", ["Accepted", "Rejected", "Expired", "Superseded", "Submitted"])
                deficiency = st.text_input("Deficiency tag", placeholder="e.g., missing sign-off, expired evidence")
                comments = st.text_area("Review comments")
                if st.form_submit_button("Record review"):
                    svc.review_document(doc_map[chosen], status, comments, deficiency, username)
                    st.success("Document review recorded and checklist recalculated.")
                    rerun()
        else:
            st.info("Evidence review is available to GCC, Data Validation, and Administrator roles.")


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
    open_only = st.toggle("Open tasks only", value=True)
    tasks = svc.get_tasks(role, username, open_only=open_only)
    safe_df(tasks, height=420)
    if tasks.empty or svc.is_read_only(role):
        return
    st.subheader("Update task")
    task_map = {f"{row['task_id']} — {row['title']}": int(row["task_id"]) for _, row in tasks.iterrows()}
    chosen = st.selectbox("Task", list(task_map.keys()))
    with st.form("update_task"):
        status = st.selectbox("Status", TASK_STATUSES)
        evidence_id = st.number_input("Closure evidence document ID", min_value=0, value=0, step=1)
        reason = st.text_area("Closure reason / response")
        if st.form_submit_button("Update task"):
            svc.update_task(task_map[chosen], status, reason, int(evidence_id) or None, username)
            st.success("Task updated.")
            rerun()


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
    if svc.is_read_only(role):
        return
    tabs = st.tabs(["Raise finding", "Update finding"])
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
                    assigned_to = st.text_input("Assigned owner", value=euc.get("owner") or "")
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
            finding_map = {f"{row['finding_id']} — {row['reference_id']} — {row['severity']} — {row['status']}": int(row["finding_id"]) for _, row in findings.iterrows()}
            chosen = st.selectbox("Finding", list(finding_map.keys()))
            with st.form("update_finding"):
                status = st.selectbox("Status", ["Open", "In Progress", "Closure Requested", "Closed", "Cancelled"])
                comments = st.text_area("Closure / validation comments")
                if st.form_submit_button("Update finding"):
                    if status == "Closed" and role not in {svc.DVU_ROLE, svc.GCC_ROLE, svc.ADMIN_ROLE}:
                        st.error("Closure validation is restricted to Data Validation, GCC, or Administrator roles.")
                    else:
                        svc.update_finding(finding_map[chosen], status, comments, username)
                        st.success("Finding updated.")
                        rerun()


def page_exceptions() -> None:
    st.title("Exceptions")
    username, role = current_user()
    exceptions = svc.get_exceptions(open_only=False)
    safe_df(exceptions, height=340)
    if svc.is_read_only(role):
        return
    tabs = st.tabs(["Create exception", "Approve / reject"])
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
    safe_df(svc.get_incidents(open_only=False), height=340)
    if svc.is_read_only(role):
        return
    euc = euc_selector("Incident EUC")
    if not euc:
        return
    if not svc.can_edit_euc(role, username, euc) and role not in {svc.GCC_ROLE, svc.ADMIN_ROLE}:
        st.info("Incident creation is available to EUC owners/delegates and governance roles.")
        return
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


def page_material_changes() -> None:
    st.title("Material Changes & Reassessments")
    username, role = current_user()
    safe_df(svc.get_material_changes(), height=330)
    if svc.is_read_only(role):
        return
    euc = euc_selector("Changed EUC")
    if not euc:
        return
    if not svc.can_edit_euc(role, username, euc) and role not in {svc.GCC_ROLE, svc.ADMIN_ROLE}:
        st.info("Material change creation is available to EUC owners/delegates and governance roles.")
        return
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
    tabs = st.tabs(["Mark industrialization candidate", "Controlled decommissioning"])
    with tabs[0]:
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
    with tabs[1]:
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
    tabs = st.tabs(["Reference data", "Required artifact rules", "Due-date rules", "Seed/reset demo"])
    with tabs[0]:
        category = st.selectbox("Category", ["document_type", "lifecycle_status", "risk_level", "control_area", "cacrt_dimension"])
        st.write("Current values")
        st.write(refs.get(category, []))
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
    with tabs[1]:
        safe_df(svc.required_rules_table(), height=320)
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
    with tabs[2]:
        safe_df(svc.due_date_rules_table(), height=360)
        st.caption("Due-date rule editing is represented in the data model. The MVP uses default seeded rules for generated tasks.")
    with tabs[3]:
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
    if "role" not in st.session_state:
        st.session_state["role"] = ROLES[0]
    if "username" not in st.session_state:
        st.session_state["username"] = svc.username_options_for_role(st.session_state["role"])[0]
    show_login()
    page = show_sidebar()
    route(page)


if __name__ == "__main__":
    main()
