"""Streamlit UI for the End-to-End EUC Governance Monitoring App."""

from __future__ import annotations

import base64
import html
import inspect
import mimetypes
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode
    AGGRID_AVAILABLE = True
except Exception:  # pragma: no cover - fallback if dependency is not installed locally
    AgGrid = None
    DataReturnMode = None
    GridOptionsBuilder = None
    GridUpdateMode = None
    AGGRID_AVAILABLE = False

import services as svc
from db import DATABASE_FILE, init_db, table_count
import schema as app_schema

APP_TITLE = getattr(app_schema, "APP_TITLE", "End-to-End EUC Governance Monitoring App")
BANK_NAME = getattr(app_schema, "BANK_NAME", "Eurobank S.A.")
APPROVAL_STATUSES = getattr(app_schema, "APPROVAL_STATUSES", ["Pending", "Approved", "Rejected", "Expired", "Withdrawn"])
BCBS239_OUTPUT_TYPES = getattr(app_schema, "BCBS239_OUTPUT_TYPES", ["Material Report", "Material KRI", "Material Model"])
BUSINESS_UNITS = getattr(app_schema, "BUSINESS_UNITS", ["Risk Management", "Finance", "Treasury", "Retail Banking", "Corporate Banking", "Group Finance", "Group Risk", "Operations", "Compliance", "Other"])
CACRT_DIMENSIONS = getattr(app_schema, "CACRT_DIMENSIONS", ["Completeness", "Accuracy", "Consistency", "Reasonableness", "Timeliness", "Traceability"])
CHANGE_TYPES = getattr(app_schema, "CHANGE_TYPES", ["Logic", "Inputs", "Outputs", "Recipients", "Thresholds", "Security", "Storage", "Dependencies", "Platform", "Other"])
CONTROL_AREAS = getattr(app_schema, "CONTROL_AREAS", ["Ownership & Accountability", "Inventory & Classification", "Data Inputs & Lineage", "Data Validation", "Change Management", "Access Control", "Operational Resilience", "Reconciliation & Controls", "Issue Management", "Decommissioning"])
CONTROLLED_STORAGE_TYPES = getattr(app_schema, "CONTROLLED_STORAGE_TYPES", ["Controlled SharePoint", "Controlled Network Drive", "Document Management System", "Code Repository", "Database", "Other"])
DIRECTORY_ROLES = getattr(app_schema, "DIRECTORY_ROLES", getattr(app_schema, "ROLES", []))
DOCUMENT_STATUSES = getattr(app_schema, "DOCUMENT_STATUSES", ["Pending", "Submitted", "Accepted", "Rejected", "Expired", "Superseded", "Missing"])
DOCUMENT_TYPES = getattr(app_schema, "DOCUMENT_TYPES", [])
FINDING_SEVERITIES = getattr(app_schema, "FINDING_SEVERITIES", ["Low", "Medium", "High", "Critical"])
FREQUENCIES = getattr(app_schema, "FREQUENCIES", ["Daily", "Weekly", "Monthly", "Quarterly", "Ad hoc", "Event-driven"])
INCIDENT_STATUSES = getattr(app_schema, "INCIDENT_STATUSES", ["Open", "Contained", "RCA In Progress", "Remediation In Progress", "Closed"])
LEGAL_ENTITIES = getattr(app_schema, "LEGAL_ENTITIES", ["Eurobank S.A.", "Eurobank Holdings", "Eurobank Cyprus", "Eurobank Bulgaria", "Eurobank Private Bank Luxembourg", "Other"])
LEVELS_OF_AUTOMATION = getattr(app_schema, "LEVELS_OF_AUTOMATION", ["Manual", "Semi-automated", "Automated", "Scheduled automated", "Other"])
LIFECYCLE_STATUSES = getattr(app_schema, "LIFECYCLE_STATUSES", [])
OVERALL_STATUSES = getattr(app_schema, "OVERALL_STATUSES", [])
PRIORITIES = getattr(app_schema, "PRIORITIES", ["Low", "Medium", "High", "Critical"])
REVIEW_OUTCOMES = getattr(app_schema, "REVIEW_OUTCOMES", ["Accepted", "Accepted with comments", "Returned for remediation", "Finding raised"])
REVIEW_TYPES = getattr(app_schema, "REVIEW_TYPES", ["Data Validation", "GCC Monitoring", "Closure Validation", "Periodic Review"])
RISK_LEVELS = getattr(app_schema, "RISK_LEVELS", ["Low", "Medium", "High", "Very High"])
ROLES = getattr(app_schema, "ROLES", ["EUC Owner", "EUC Owner Delegate / Contributor", "GCC", "Data Validation Unit", "Group IT Governance Administrator", "Approver / Head of Unit", "Internal Audit / Read-only User"])
TASK_STATUSES = getattr(app_schema, "TASK_STATUSES", ["Open", "In Progress", "Blocked", "Closure Requested", "Closed", "Cancelled"])
TASK_TYPES = getattr(app_schema, "TASK_TYPES", [])
TECHNOLOGY_TYPES = getattr(app_schema, "TECHNOLOGY_TYPES", ["Excel", "Access", "Python script", "Notebook", "Report", "SQL script", "Manual process", "Other"])
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
    "Email Notifications",
    "Audit Trail",
]

REPORTS_ACCESS_ROLES = {svc.GCC_ROLE, svc.ADMIN_ROLE, svc.DVU_ROLE}
NOTIFICATION_ACCESS_ROLES = {svc.GCC_ROLE, svc.ADMIN_ROLE, svc.DVU_ROLE}
AUDIT_ACCESS_ROLES = {svc.GCC_ROLE}

# Role-scoped page access. These sets drive both the compact grouped menu and
# direct page-access guards. Group IT Governance Administrator is intentionally
# limited to platform/configuration/reporting functions and does not receive
# EUC content, risk-assessment, evidence-review or operational workflow pages.
PAGE_ACCESS_ROLES = {
    "Home / Dashboard": set(ROLES),
    "EUC Inventory": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.READ_ONLY_ROLE},
    "Register New EUC": {svc.OWNER_ROLE},
    "EUC Detail View": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.APPROVER_ROLE, svc.READ_ONLY_ROLE},
    "Components / Assets": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE},
    "Risk Assessment": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.READ_ONLY_ROLE},
    "Documents & Evidence Pack": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.APPROVER_ROLE, svc.READ_ONLY_ROLE},
    "Required Artifact Checklist": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.READ_ONLY_ROLE},
    "Tasks & Remediation": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.APPROVER_ROLE},
    "Data Validation Review Queue": {svc.DVU_ROLE},
    "GCC Monitoring View": {svc.GCC_ROLE},
    "Findings & Challenge Management": {svc.GCC_ROLE, svc.DVU_ROLE, svc.READ_ONLY_ROLE},
    "Exceptions": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.APPROVER_ROLE, svc.READ_ONLY_ROLE},
    "Incidents & Near Misses": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.READ_ONLY_ROLE},
    "Material Changes & Reassessments": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.DVU_ROLE, svc.READ_ONLY_ROLE},
    "Industrialization & Decommissioning": {svc.OWNER_ROLE, svc.CONTRIBUTOR_ROLE, svc.GCC_ROLE, svc.READ_ONLY_ROLE},
    "Reports & KPIs": REPORTS_ACCESS_ROLES,
    "Admin Configuration": {svc.ADMIN_ROLE},
    "Email Notifications": NOTIFICATION_ACCESS_ROLES,
    "Audit Trail": AUDIT_ACCESS_ROLES,
}

NAVIGATION_GROUPS = [
    (
        "My Work",
        ["Home / Dashboard", "EUC Inventory", "EUC Detail View", "Tasks & Remediation"],
    ),
    (
        "EUC Lifecycle",
        [
            "Register New EUC",
            "Components / Assets",
            "Risk Assessment",
            "Documents & Evidence Pack",
            "Required Artifact Checklist",
            "Material Changes & Reassessments",
            "Incidents & Near Misses",
            "Exceptions",
            "Industrialization & Decommissioning",
        ],
    ),
    (
        "Review & Oversight",
        [
            "Data Validation Review Queue",
            "GCC Monitoring View",
            "Findings & Challenge Management",
            "Reports & KPIs",
            "Email Notifications",
            "Audit Trail",
        ],
    ),
    (
        "Administration",
        ["Admin Configuration"],
    ),
]

WORKBENCH_ACTIONS_BY_ROLE = {
    svc.OWNER_ROLE: [
        ("Register New EUC", "Create a new EUC application record"),
        ("Risk Assessment", "Complete or review your EUC risk assessments"),
        ("Documents & Evidence Pack", "Upload required evidence and review checklist status"),
        ("Tasks & Remediation", "Work on tasks assigned to you"),
        ("Material Changes & Reassessments", "Record a material change and trigger reassessment"),
        ("Exceptions", "Raise or monitor an exception request"),
    ],
    svc.CONTRIBUTOR_ROLE: [
        ("EUC Inventory", "Open EUCs delegated to you"),
        ("Risk Assessment", "Assist with submitted or amended assessments"),
        ("Documents & Evidence Pack", "Upload evidence for delegated EUCs"),
        ("Tasks & Remediation", "Work on tasks assigned to you"),
        ("Material Changes & Reassessments", "Record change information for delegated EUCs"),
        ("Incidents & Near Misses", "Log incident information for delegated EUCs"),
    ],
    svc.DVU_ROLE: [
        ("Data Validation Review Queue", "Review EUCs ready for independent validation"),
        ("Risk Assessment", "Review submitted risk assessments"),
        ("Documents & Evidence Pack", "Review evidence submissions"),
        ("Findings & Challenge Management", "Raise or manage findings"),
        ("Tasks & Remediation", "Review your validation task queue"),
        ("Reports & KPIs", "Use policy MI and KPI reports"),
    ],
    svc.GCC_ROLE: [
        ("GCC Monitoring View", "Monitor portfolio risk, gaps and events"),
        ("Findings & Challenge Management", "Govern findings and remediation"),
        ("Exceptions", "Monitor and challenge exception records"),
        ("Incidents & Near Misses", "Monitor incident and near-miss records"),
        ("Reports & KPIs", "Run policy MI and KPI reports"),
        ("Audit Trail", "Inspect immutable audit activity"),
    ],
    svc.ADMIN_ROLE: [
        ("Admin Configuration", "Maintain users, reference data, BCBS outputs and system rules"),
        ("Email Notifications", "Monitor RACI notification outbox and rules"),
        ("Reports & KPIs", "Run portfolio reports without editing EUC content"),
    ],
    svc.APPROVER_ROLE: [
        ("Tasks & Remediation", "Review tasks assigned to you"),
        ("Exceptions", "Approve or reject exception requests"),
        ("EUC Detail View", "View supporting EUC and evidence context"),
        ("Documents & Evidence Pack", "View supporting evidence"),
    ],
    svc.READ_ONLY_ROLE: [
        ("EUC Inventory", "View EUCs available to audit/read-only users"),
        ("EUC Detail View", "Inspect EUC records and history"),
        ("Documents & Evidence Pack", "View evidence records"),
        ("Risk Assessment", "View risk assessment history"),
        ("Findings & Challenge Management", "View findings"),
        ("Exceptions", "View exceptions"),
    ],
}


def can_access_page(page: str, role: str) -> bool:
    """Central page-access guard for role-sensitive navigation items."""
    return role in PAGE_ACCESS_ROLES.get(page, set())


def navigation_for_role(role: str) -> list[str]:
    """Return only the pages the current role is allowed to open."""
    return [page for page in NAVIGATION if can_access_page(page, role)]


def navigation_groups_for_role(role: str) -> list[tuple[str, list[str]]]:
    """Return grouped navigation entries after applying page access rules."""
    groups: list[tuple[str, list[str]]] = []
    for group_name, pages in NAVIGATION_GROUPS:
        allowed = [page for page in pages if can_access_page(page, role)]
        if allowed:
            groups.append((group_name, allowed))
    return groups


def set_selected_page(page: str) -> None:
    """Set the current page and rerun to emulate navigation buttons."""
    st.session_state["selected_page"] = page
    rerun()

def bootstrap() -> None:
    init_db()
    svc.initialize_reference_data("system")
    # Do not auto-seed EUC operational data on startup. Demo data can be
    # loaded explicitly from Admin Configuration -> Seed/reset demo.


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


def _grid_height(height: int | str | None, df: pd.DataFrame) -> int:
    """Return a safe grid height for Streamlit/AgGrid tables."""
    if isinstance(height, int) and height > 0:
        return height
    if isinstance(height, str) and height == "auto":
        return min(620, max(180, 40 + 36 * (len(df) + 1)))
    return min(560, max(220, 44 + 36 * min(len(df) + 1, 12)))


def _grid_key(df: pd.DataFrame, prefix: str = "grid") -> str:
    """Create a collision-resistant key for read-only grid render calls."""
    return f"{prefix}_{id(df)}_{len(df)}_{abs(hash(tuple(map(str, df.columns)))) % 100000}"


def _labelize_column(column: Any) -> str:
    """Return a readable table header from a dataframe column name."""
    text = str(column).strip()
    replacements = {
        "euc": "EUC",
        "id": "ID",
        "bcbs239": "BCBS 239",
        "cacrt": "CACRT",
        "cde": "CDE",
        "kri": "KRI",
        "sla": "SLA",
        "spof": "SPOF",
        "uat": "UAT",
        "rca": "RCA",
        "raci": "RACI",
        "iof": "IOF",
        "rrf": "RRF",
        "op": "OP",
        "url": "URL",
    }
    parts = text.replace("/", " / ").replace("_", " ").split()
    rendered: list[str] = []
    for part in parts:
        key = part.lower()
        rendered.append(replacements.get(key, part.capitalize()))
    return " ".join(rendered)


def _estimate_grid_column_width(series: Any, header: str) -> int:
    """Estimate a readable AgGrid width while tolerating duplicate columns.

    Pandas returns a DataFrame rather than a Series when a dataframe contains
    duplicate column names and is accessed as df[column]. This helper must not
    assume a Series, because joined reporting/asset datasets can occasionally
    contain duplicate names after migrations or user-defined custom reports.
    """
    name = str(header or "").lower()
    try:
        if isinstance(series, pd.DataFrame):
            sample_values: list[str] = []
            for col in series.columns[:3]:
                sample_values.extend(series[col].dropna().astype(str).head(20).tolist())
            sample = sample_values[:50]
        else:
            sample = series.dropna().astype(str).head(50).tolist()
            name = str(getattr(series, "name", header) or header).lower()
    except Exception:
        sample = []
    longest_value = max([len(str(header)), *[len(v) for v in sample]], default=len(str(header)))

    if name.endswith("_id") or name in {"id", "version", "mandatory", "active", "active_flag"}:
        return max(95, min(150, 18 + longest_value * 7))
    if any(token in name for token in ["description", "comments", "rationale", "summary", "what_to_upload", "finding_description", "remediation", "impact_assessment"]):
        return max(280, min(520, 28 + longest_value * 7))
    if any(token in name for token in ["file_path", "storage_location", "bcbs239_output_mapping", "report", "output", "requirement"]):
        return max(220, min(440, 28 + longest_value * 7))
    if any(token in name for token in ["date", "at", "due", "expiry", "review"]):
        return max(140, min(210, 28 + longest_value * 7))
    return max(160, min(360, 28 + longest_value * 7))


def _deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a dataframe with unique column names for AgGrid.

    AgGrid and Pandas column lookups are more predictable when every column name
    is unique. Duplicate names are preserved with a numbered suffix for display
    rather than causing runtime failures in grid configuration.
    """
    if df is None or df.empty:
        return df
    seen: dict[str, int] = {}
    columns: list[str] = []
    changed = False
    for col in df.columns:
        base = str(col)
        count = seen.get(base, 0)
        if count:
            columns.append(f"{base}_{count + 1}")
            changed = True
        else:
            columns.append(base)
        seen[base] = count + 1
    if not changed:
        return df
    out = df.copy()
    out.columns = columns
    return out


def _build_grid_options(
    df: pd.DataFrame,
    *,
    selection_mode: str | None = None,
    use_checkbox: bool = False,
) -> dict[str, Any]:
    """Create readable Excel-like AgGrid options with filters on every column."""
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        filter=True,
        floatingFilter=True,
        sortable=True,
        resizable=True,
        wrapText=True,
        autoHeight=True,
        wrapHeaderText=True,
        autoHeaderHeight=True,
        minWidth=150,
        cellStyle={"whiteSpace": "normal", "lineHeight": "1.25"},
    )
    for column in df.columns:
        header = _labelize_column(column)
        width = _estimate_grid_column_width(df[column], header)
        gb.configure_column(
            column,
            headerName=header,
            headerTooltip=header,
            tooltipField=column,
            width=width,
            minWidth=min(width, 180),
            wrapText=True,
            autoHeight=True,
        )
    gb.configure_grid_options(
        enableCellTextSelection=True,
        ensureDomOrder=True,
        suppressMenuHide=False,
        animateRows=False,
        tooltipShowDelay=250,
        rowHeight=44,
        headerHeight=58,
        floatingFiltersHeight=34,
        suppressColumnVirtualisation=False,
        alwaysShowHorizontalScroll=True,
        alwaysShowVerticalScroll=True,
    )
    if selection_mode:
        gb.configure_selection(selection_mode=selection_mode, use_checkbox=use_checkbox)
    return gb.build()




def _aggrid_event_kwargs(*, read_only: bool, selection: bool = False) -> dict[str, Any]:
    """Return AgGrid event settings that avoid page reruns while typing filters.

    For read-only tables, filtering/sorting/resizing should stay client-side. Some
    streamlit-aggrid versions rerun Streamlit on filter changes unless update_on
    is explicitly empty. Selection tables still need a rerun on row selection.
    """
    if not AGGRID_AVAILABLE:
        return {}
    try:
        params = inspect.signature(AgGrid).parameters
    except Exception:
        params = {}
    if "update_on" in params:
        if selection:
            return {"update_on": ["selectionChanged"]}
        if read_only:
            return {"update_on": []}
    if selection:
        return {"update_mode": GridUpdateMode.SELECTION_CHANGED}
    if read_only:
        return {"update_mode": GridUpdateMode.NO_UPDATE}
    return {}

def safe_df(df: pd.DataFrame, height: int | str | None = None, *, key: str | None = None) -> None:
    """Render a user-facing table with in-grid filters on every column.

    AgGrid gives users Excel-like column filters, sorting, resizing and search
    menus inside the table itself. If the optional component is unavailable, the
    function falls back to Streamlit's native dataframe without passing invalid
    height values.
    """
    if df is None or df.empty:
        st.info("No records found for the current filters.")
        return

    display_df = _deduplicate_columns(df.copy())
    if AGGRID_AVAILABLE:
        AgGrid(
            display_df,
            gridOptions=_build_grid_options(display_df),
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            fit_columns_on_grid_load=False,
            **_aggrid_event_kwargs(read_only=True),
            allow_unsafe_jscode=False,
            theme="streamlit",
            height=_grid_height(height, display_df),
            key=key or _grid_key(display_df),
        )
        return

    kwargs: dict[str, Any] = {"use_container_width": True, "hide_index": True}
    if isinstance(height, int) and height > 0:
        kwargs["height"] = height
    elif isinstance(height, str) and height == "auto":
        kwargs["height"] = "auto"
    st.dataframe(display_df, **kwargs)



def detail_df(df: pd.DataFrame, height: int | str | None = None) -> None:
    """Render small detail/summary tables with Streamlit native rendering.

    AgGrid is used for operational list/report tables. For compact detail panels
    such as assessment review sections, native rendering is more reliable and
    avoids blank iframe-like areas in embedded sections while preserving full
    wording and valid height handling.
    """
    if df is None or df.empty:
        st.info("No records found for the current filters.")
        return
    kwargs: dict[str, Any] = {"use_container_width": True, "hide_index": True}
    if isinstance(height, int) and height > 0:
        kwargs["height"] = height
    elif isinstance(height, str) and height == "auto":
        kwargs["height"] = "auto"
    st.dataframe(df, **kwargs)

def selectable_df(
    df: pd.DataFrame,
    *,
    key: str,
    height: int | str | None = None,
    selection_mode: str = "single",
) -> list[dict[str, Any]]:
    """Render an AgGrid selection table and return selected row dictionaries."""
    if df is None or df.empty:
        st.info("No records found for the current filters.")
        return []

    display_df = _deduplicate_columns(df.copy())
    if not AGGRID_AVAILABLE:
        safe_df(display_df, height=height, key=key)
        return []

    response = AgGrid(
        display_df,
        gridOptions=_build_grid_options(display_df, selection_mode=selection_mode, use_checkbox=True),
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=False,
        **_aggrid_event_kwargs(read_only=False, selection=True),
        allow_unsafe_jscode=False,
        theme="streamlit",
        height=_grid_height(height, display_df),
        key=key,
    )
    selected = response.get("selected_rows", []) if isinstance(response, dict) else []
    if isinstance(selected, pd.DataFrame):
        return selected.to_dict("records")
    if isinstance(selected, list):
        return selected
    return []


def filter_dataframe_all_fields(
    df: pd.DataFrame,
    key_prefix: str,
    *,
    title: str = "Filter table",
    expanded: bool = False,
) -> pd.DataFrame:
    """Provide per-column filters for every dataframe field.

    The Required Artifact Checklist has mixed text/status/date fields and users
    need to filter all of them without exporting to CSV. Low-cardinality columns
    receive multi-select filters; high-cardinality columns receive contains-text
    filters. A global search is also applied across every visible field.
    """
    if df is None or df.empty:
        return df

    working = df.copy()
    # Convert object-like values to strings only for matching, not for display.
    with st.expander(title, expanded=expanded):
        global_search = st.text_input(
            "Search all fields",
            key=f"{key_prefix}_global_search",
            placeholder="Type any text to search across all checklist columns",
        ).strip()
        if global_search:
            haystack = working.fillna("").astype(str).agg(" | ".join, axis=1)
            working = working[haystack.str.contains(global_search, case=False, regex=False, na=False)]

        if working.empty:
            st.caption("No rows match the global search.")
            return working

        st.caption("Column filters apply in addition to the global search.")
        filter_cols = st.columns(3)
        for idx, col_name in enumerate(df.columns):
            col_series = working[col_name] if col_name in working.columns else df[col_name]
            non_null = col_series.dropna()
            as_text = non_null.astype(str).map(str.strip)
            unique_values = sorted(v for v in as_text.unique().tolist() if v not in {"", "nan", "None"})
            label = str(col_name).replace("_", " ").title()
            container = filter_cols[idx % 3]

            if len(unique_values) == 0:
                continue
            if len(unique_values) <= 30:
                selected_values = container.multiselect(
                    label,
                    unique_values,
                    default=[],
                    key=f"{key_prefix}_filter_{col_name}",
                )
                if selected_values:
                    working = working[
                        working[col_name].fillna("").astype(str).str.strip().isin(selected_values)
                    ]
            else:
                contains_value = container.text_input(
                    f"{label} contains",
                    key=f"{key_prefix}_filter_{col_name}",
                    placeholder="Contains...",
                ).strip()
                if contains_value:
                    working = working[
                        working[col_name].fillna("").astype(str).str.contains(
                            contains_value, case=False, regex=False, na=False
                        )
                    ]

        st.caption(f"Showing {len(working)} of {len(df)} row(s).")
    return working




def resolve_uploaded_file_path(file_path: Any) -> Path | None:
    """Resolve a stored uploaded-document path to a local file path."""
    if file_path is None or str(file_path).strip() == "" or str(file_path) == "nan":
        return None
    path = Path(str(file_path))
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


def _infer_office_extension(path: Path) -> str | None:
    """Infer common Office extensions when a browser-supplied file name has no suffix."""
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
            if "xl/workbook.xml" in names:
                return ".xlsm" if "xl/vbaProject.bin" in names else ".xlsx"
            if "word/document.xml" in names:
                return ".docx"
            if "ppt/presentation.xml" in names:
                return ".pptx"
        header = path.read_bytes()[:16]
        if header.startswith(b"%PDF"):
            return ".pdf"
        if header.startswith(b"\x89PNG"):
            return ".png"
        if header.startswith(b"\xff\xd8\xff"):
            return ".jpg"
    except Exception:
        return None
    return None


def document_download_name(file_name: Any, path: Path) -> str:
    """Return a user-friendly download name with an extension where possible."""
    raw_name = str(file_name or path.name or "uploaded_document").strip() or "uploaded_document"
    if Path(raw_name).suffix:
        return raw_name
    inferred = _infer_office_extension(path)
    return f"{raw_name}{inferred}" if inferred else raw_name


def uploaded_file_data_url(file_path: Any, file_name: Any = None) -> str | None:
    """Return a browser-preview data URL for previewable locally stored files.

    Binary Office evidence should be downloaded with st.download_button instead.
    Data URLs are kept only for browser-previewable evidence such as PDF, images,
    text, and CSV. This avoids the blank/generic `download` files produced by
    browser handling of binary data URLs.
    """
    path = resolve_uploaded_file_path(file_path)
    if path is None or not path.exists() or not path.is_file():
        return None
    download_name = document_download_name(file_name, path)
    mime_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
    previewable = (
        mime_type == "application/pdf"
        or mime_type.startswith("image/")
        or mime_type.startswith("text/")
        or mime_type in {"text/csv", "application/json", "application/xml"}
    )
    if not previewable:
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_document_open_links(docs: pd.DataFrame, title: str = "Open uploaded documentation") -> None:
    """Render reliable document access controls for uploaded evidence records."""
    if docs is None or docs.empty:
        return
    st.markdown(f"#### {title}")
    for _, row in docs.iterrows():
        document_id = row.get("document_id", "")
        file_name = row.get("file_name") or f"Document {document_id}"
        document_type = row.get("document_type") or "Evidence"
        status = row.get("status") or ""
        path = resolve_uploaded_file_path(row.get("file_path"))
        if path is None or not path.exists() or not path.is_file():
            st.warning(f"File is not available in local storage for document {document_id}: {file_name}")
            continue

        download_name = document_download_name(file_name, path)
        mime_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
        label = f"Document {document_id} — {document_type} — {download_name} ({status})"
        st.caption(label)
        c1, c2 = st.columns([1, 3])
        with c1:
            st.download_button(
                "Download",
                data=path.read_bytes(),
                file_name=download_name,
                mime=mime_type,
                key=f"download_doc_{document_id}_{abs(hash(str(title))) % 100000}",
            )
        with c2:
            preview_url = uploaded_file_data_url(path, download_name)
            if preview_url:
                st.markdown(
                    f'<a href="{preview_url}" target="_blank" rel="noopener noreferrer">Open preview in browser</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Office/binary files download to your computer; open them with the relevant desktop application.")

def csv_download(df: pd.DataFrame, file_name: str, label: str = "Download CSV") -> None:
    if df is not None and not df.empty:
        st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=file_name, mime="text/csv")


def option_index(options: list[str], value: str | None, default: int = 0) -> int:
    if value in options:
        return options.index(value)
    return default


WORKING_DAY_OPTIONS = list(range(1, 91))

def _working_day_index(value: Any, default: int = 0) -> int:
    """Return a selectbox index for a stored working-day value."""
    if value is None:
        return default
    match = re.search(r"\d+", str(value))
    if not match:
        return default
    try:
        number = int(match.group(0))
    except ValueError:
        return default
    if 1 <= number <= 90:
        return number - 1
    return default


def working_day_selectbox(label: str, value: Any = None, *, key: str | None = None, help: str | None = None) -> str:
    """Select a business-working-day number and store it in a readable form."""
    selected = st.selectbox(
        label,
        WORKING_DAY_OPTIONS,
        index=_working_day_index(value),
        format_func=lambda day: f"Working day {day}",
        help=help,
        key=key,
    )
    return f"Working day {selected}"

def bcbs_output_selectbox(label: str, value: str | None = None, key: str | None = None) -> str:
    """Controlled selector for primary BCBS 239 output mapping."""
    options = [""] + svc.bcbs239_output_options(active_only=True)
    current = (value or "").strip()
    if current and current not in options:
        options.append(current)
    return st.selectbox(
        label,
        options,
        index=option_index(options, current, 0),
        format_func=lambda x: "Select BCBS 239 material report/output" if x == "" else x,
        help="Primary mapping is mandatory and cannot be Not Applicable. Values come from the controlled BCBS 239 material reports inventory.",
        key=key,
    )




def reference_selectbox(category: str, label: str, fallback: list[str], value: str | None = None, *, key: str | None = None, help: str | None = None) -> str:
    options = svc.reference_options(category, fallback=fallback, include_blank=False)
    current = (value or "").strip()
    if current and current not in options:
        options.append(current)
    return st.selectbox(label, options, index=option_index(options, current, 0), key=key, help=help)


def user_selectbox(label: str, value: str | None = None, *, key: str | None = None, include_blank: bool = False, role: str | None = None, help: str | None = None) -> str:
    options = svc.active_user_options(role=role, include_blank=include_blank)
    current = (value or "").strip()
    if current and current not in options:
        options.append(current)
    return st.selectbox(label, options, index=option_index(options, current, 0), key=key, help=help)


def bcbs_material_selectbox(label: str, output_type: str, value: str | None = None, *, key: str | None = None) -> str:
    options = ["Not Applicable"] + svc.bcbs239_output_options(active_only=True, output_type=output_type)
    current = (value or "Not Applicable").strip()
    if current and current not in options:
        options.append(current)
    return st.selectbox(
        label,
        options,
        index=option_index(options, current, 0),
        key=key,
        help=f"Select the relevant {output_type.lower()} or Not Applicable. Values are maintained in Admin Configuration > BCBS 239 outputs.",
    )



def bcbs_any_mapping_selectbox(label: str, value: str | None = None, *, key: str | None = None, include_blank: bool = True) -> str:
    options: list[str] = []
    if include_blank:
        options.append("")
    for output_type in BCBS239_OUTPUT_TYPES:
        for item in svc.bcbs239_output_options(active_only=True, output_type=output_type):
            if item not in options:
                options.append(item)
    current = (value or "").strip()
    if current and current not in options:
        options.append(current)
    return st.selectbox(
        label,
        options,
        index=option_index(options, current, 0),
        format_func=lambda x: "Select mapped report / KRI / model" if x == "" else x,
        key=key,
    )


def display_value(value: Any) -> str:
    """Return a business-friendly display value for table/card views."""
    if value is None:
        return "—"
    if isinstance(value, float) and pd.isna(value):
        return "—"
    text = str(value)
    if text.strip() == "" or text.lower() in {"nan", "none", "null"}:
        return "—"
    return text


def labelize(field_name: str) -> str:
    return field_name.replace("_", " ").strip().title()


def record_table(record: dict[str, Any], fields: list[str | tuple[str, str]], *, title: str | None = None) -> None:
    """Render a record as a normal field/value table instead of raw JSON."""
    rows: list[dict[str, str]] = []
    for item in fields:
        if isinstance(item, tuple):
            label, key = item
        else:
            label, key = labelize(item), item
        rows.append({"Field": label, "Value": display_value(record.get(key))})
    if title:
        st.markdown(f"#### {title}")
    detail_df(pd.DataFrame(rows), height="auto")


def assessment_review_card(assessment: dict[str, Any]) -> None:
    """Render a completed risk assessment in workbook-style business sections."""
    st.markdown(
        f"#### Assessment {display_value(assessment.get('assessment_id'))} "
        f"— Version {display_value(assessment.get('version'))}"
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Assessment date", display_value(assessment.get("assessment_date")))
    c2.metric("Assessed by", display_value(assessment.get("assessed_by")))
    c3.metric("Review status", display_value(assessment.get("status") or "Submitted"))
    c4.metric("Overall inherent risk", display_value(assessment.get("overall_inherent_risk") or assessment.get("inherent_risk")))
    c5.metric("Overall residual risk", display_value(assessment.get("overall_residual_risk") or assessment.get("residual_risk")))

    st.markdown("##### BCBS 239 materiality")
    record_table(
        assessment,
        [
            ("Could materially affect BCBS 239 output", "materiality_q1"),
            ("Key control point", "materiality_q2"),
            ("Single point of failure", "materiality_q3"),
            ("Materially supports BCBS 239", "materially_supports_bcbs239"),
            ("Assessment type", "trigger_type"),
        ],
    )

    st.markdown("##### Risk dimensions")
    dimensions = pd.DataFrame(
        [
            {
                "Dimension": "Integrity / Accuracy",
                "Owner inherent": display_value(assessment.get("owner_integrity_inherent")),
                "Effective inherent": display_value(assessment.get("effective_integrity_inherent") or assessment.get("inherent_risk")),
                "Control effectiveness": display_value(assessment.get("integrity_control_effectiveness")),
                "Residual risk": display_value(assessment.get("integrity_residual_risk") or assessment.get("residual_risk")),
            },
            {
                "Dimension": "Timeliness / Availability",
                "Owner inherent": display_value(assessment.get("owner_timeliness_inherent")),
                "Effective inherent": display_value(assessment.get("effective_timeliness_inherent") or assessment.get("inherent_risk")),
                "Control effectiveness": display_value(assessment.get("timeliness_control_effectiveness")),
                "Residual risk": display_value(assessment.get("timeliness_residual_risk") or assessment.get("residual_risk")),
            },
        ]
    )
    detail_df(dimensions, height=180)

    st.markdown("##### Baseline controls")
    effective_reg_status = svc.effective_registration_control_status(assessment)
    controls = pd.DataFrame(
        [
            {
                "Control": "Registration & risk assessment",
                "Selected status": display_value(assessment.get("control_registration_risk_assessment")),
                "Effective status": display_value(effective_reg_status),
            },
            {"Control": "Privileged Access", "Selected status": display_value(assessment.get("control_privileged_access")), "Effective status": display_value(assessment.get("control_privileged_access"))},
            {"Control": "Versioning & change log", "Selected status": display_value(assessment.get("control_versioning_change_log")), "Effective status": display_value(assessment.get("control_versioning_change_log"))},
            {"Control": "Checks & reconciliations", "Selected status": display_value(assessment.get("control_checks_reconciliations")), "Effective status": display_value(assessment.get("control_checks_reconciliations"))},
            {"Control": "EUC Library of Controls / CACRT", "Selected status": display_value(assessment.get("control_library_controls_cacrt")), "Effective status": display_value(assessment.get("control_library_controls_cacrt"))},
            {"Control": "Operating Procedure", "Selected status": display_value(assessment.get("control_operating_procedure")), "Effective status": display_value(assessment.get("control_operating_procedure"))},
            {"Control": "Evidence & sign-off", "Selected status": display_value(assessment.get("control_evidence_signoff")), "Effective status": display_value(assessment.get("control_evidence_signoff"))},
            {"Control": "Resilience", "Selected status": display_value(assessment.get("control_resilience")), "Effective status": display_value(assessment.get("control_resilience"))},
        ]
    )
    detail_df(controls, height=340)

    st.markdown("##### Required action and rationale")
    record_table(
        assessment,
        [
            ("Required action", "required_action"),
            ("Rationale / comments", "rationale"),
            ("Reviewed by", "reviewed_by"),
            ("Review comments", "review_comments"),
            ("Created at", "created_at"),
        ],
    )



def risk_assessment_input_form(
    form_key: str,
    euc: dict[str, Any],
    username: str,
    defaults: dict[str, Any] | None = None,
    submit_label: str = "Submit assessment",
) -> dict[str, Any] | None:
    """Render the Excel-aligned risk-assessment form and return a payload on submit."""
    defaults = defaults or {}
    with st.form(form_key):
        st.markdown("#### BCBS 239 materiality assessment")
        m1 = st.selectbox(
            "Failure/error could make a BCBS 239 in-scope output materially inaccurate, incomplete, delayed, or unavailable",
            ["No", "Yes"],
            index=option_index(["No", "Yes"], defaults.get("materiality_q1") or "No"),
            key=f"{form_key}_m1",
        )
        m2 = st.selectbox(
            "EUC is a key control point that can trigger correction, rejection, restatement, escalation, or delayed issuance",
            ["No", "Yes"],
            index=option_index(["No", "Yes"], defaults.get("materiality_q2") or "No"),
            key=f"{form_key}_m2",
        )
        m3 = st.selectbox(
            "EUC is a single point of failure in a critical reporting/risk process",
            ["No", "Yes"],
            index=option_index(["No", "Yes"], defaults.get("materiality_q3") or "No"),
            key=f"{form_key}_m3",
        )

        st.markdown("#### Owner-entered inherent risk")
        c1, c2, c3 = st.columns(3)
        owner_integrity = c1.selectbox(
            "Owner Integrity / Accuracy inherent risk",
            svc.OWNER_INHERENT_LEVELS,
            index=option_index(svc.OWNER_INHERENT_LEVELS, defaults.get("owner_integrity_inherent") or "Medium"),
            key=f"{form_key}_owner_integrity",
        )
        owner_timeliness = c2.selectbox(
            "Owner Timeliness / Availability inherent risk",
            svc.OWNER_INHERENT_LEVELS,
            index=option_index(svc.OWNER_INHERENT_LEVELS, defaults.get("owner_timeliness_inherent") or "Medium"),
            key=f"{form_key}_owner_timeliness",
        )
        trigger_options = ["Periodic", "Material Change", "Incident-triggered", "Initial Registration", "Manual / Ad hoc"]
        trigger = c3.selectbox(
            "Assessment type",
            trigger_options,
            index=option_index(trigger_options, defaults.get("trigger_type") or "Periodic"),
            key=f"{form_key}_trigger",
        )

        st.markdown("#### Baseline controls")
        readiness = svc.registration_control_readiness(int(euc["euc_id"]))
        missing_text = ", ".join(readiness["missing_items"]) if readiness["missing_items"] else "None"
        st.info(
            "Registration & Risk Assessment readiness: "
            f"registration complete = {readiness['registration_complete']}; "
            f"accepted risk assessment exists = {readiness['accepted_risk_assessment']}; "
            f"maximum effective status now = {readiness['allowed_status']}; "
            f"missing items = {missing_text}."
        )

        def control_selector(container, label: str, key: str, options: list[str], default: str | None) -> str:
            container.caption(svc.BASELINE_CONTROL_GUIDANCE[key])
            return container.selectbox(
                label,
                options,
                index=option_index(options, default or "Partially in place"),
                help=svc.BASELINE_CONTROL_GUIDANCE[key],
                key=f"{form_key}_{key}",
            )

        a, b = st.columns(2)
        ctrl_1 = control_selector(a, "1. Registration & risk assessment", "registration_risk_assessment", svc.CONTROL_STATUS_CORE, defaults.get("control_registration_risk_assessment"))
        if svc.CONTROL_STATUS_RANK.get(ctrl_1, 1) > svc.CONTROL_STATUS_RANK.get(readiness["allowed_status"], 1):
            st.warning(
                "For this submission, Registration & Risk Assessment will be treated as "
                f"{readiness['allowed_status']} for the calculation until registration/mapping is complete and the risk assessment is Accepted by an independent reviewer."
            )
        ctrl_2 = control_selector(b, "2. Privileged Access", "privileged_access", svc.CONTROL_STATUS_CORE, defaults.get("control_privileged_access"))
        ctrl_3 = control_selector(a, "3. Versioning & change log", "versioning_change_log", svc.CONTROL_STATUS_CORE, defaults.get("control_versioning_change_log"))
        ctrl_4 = control_selector(b, "4. Checks & reconciliations", "checks_reconciliations", svc.CONTROL_STATUS_CORE, defaults.get("control_checks_reconciliations"))
        ctrl_5 = control_selector(a, "5. EUC Library of Controls / CACRT", "library_controls_cacrt", svc.CONTROL_STATUS_WITH_NA, defaults.get("control_library_controls_cacrt"))
        ctrl_6 = control_selector(b, "6. Operating Procedure", "operating_procedure", svc.CONTROL_STATUS_CORE, defaults.get("control_operating_procedure"))
        ctrl_7 = control_selector(a, "7. Evidence & sign-off", "evidence_signoff", svc.CONTROL_STATUS_WITH_NA, defaults.get("control_evidence_signoff"))
        ctrl_8 = control_selector(b, "8. Resilience", "resilience", svc.CONTROL_STATUS_CORE, defaults.get("control_resilience"))

        rationale = st.text_area("Rationale / comments", value=defaults.get("rationale") or "", key=f"{form_key}_rationale")
        submitted = st.form_submit_button(submit_label, type="primary")
        if not submitted:
            return None
        return {
            "euc_id": euc["euc_id"],
            "assessment_date": date.today().isoformat(),
            "assessed_by": username,
            "materiality_q1": m1,
            "materiality_q2": m2,
            "materiality_q3": m3,
            "owner_integrity_inherent": owner_integrity,
            "owner_timeliness_inherent": owner_timeliness,
            "control_registration_risk_assessment": ctrl_1,
            "control_privileged_access": ctrl_2,
            "control_versioning_change_log": ctrl_3,
            "control_checks_reconciliations": ctrl_4,
            "control_library_controls_cacrt": ctrl_5,
            "control_operating_procedure": ctrl_6,
            "control_evidence_signoff": ctrl_7,
            "control_resilience": ctrl_8,
            "trigger_type": trigger,
            "rationale": rationale,
        }


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

    allowed_pages = navigation_for_role(role)
    if not allowed_pages:
        allowed_pages = ["Home / Dashboard"]

    selected_page = st.session_state.get("selected_page", "Home / Dashboard")
    if selected_page not in allowed_pages:
        selected_page = "Home / Dashboard" if "Home / Dashboard" in allowed_pages else allowed_pages[0]
        st.session_state["selected_page"] = selected_page

    st.sidebar.markdown("### Navigation")
    for group_name, pages in navigation_groups_for_role(role):
        st.sidebar.markdown(f"**{group_name}**")
        for page in pages:
            is_current = page == selected_page
            label = f"➤ {page}" if is_current else page
            if st.sidebar.button(label, key=f"nav_{group_name}_{page}", use_container_width=True, disabled=is_current):
                st.session_state["selected_page"] = page
                rerun()
        st.sidebar.caption(" ")

    st.sidebar.divider()
    st.sidebar.caption(f"SQLite: `{DATABASE_FILE.name}` · Uploads: `/uploads`")
    return st.session_state.get("selected_page", selected_page)


def metric_grid(metrics: dict[str, int]) -> None:
    rows = [list(metrics.items())[i : i + 5] for i in range(0, len(metrics), 5)]
    for row in rows:
        cols = st.columns(len(row))
        for col, (label, value) in zip(cols, row):
            col.metric(label, value)


def render_role_workbench(role: str) -> None:
    """Role-specific action cards for the Home page."""
    actions = [(page, desc) for page, desc in WORKBENCH_ACTIONS_BY_ROLE.get(role, []) if can_access_page(page, role)]
    if not actions:
        return
    st.subheader("Role workbench")
    st.caption("Quick actions are scoped to the current role. Portfolio monitoring and administration actions appear only for the roles that own those responsibilities.")
    for start in range(0, len(actions), 3):
        cols = st.columns(3)
        for col, (page, description) in zip(cols, actions[start : start + 3]):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{page}**")
                    st.caption(description)
                    if st.button("Open", key=f"workbench_{role}_{page}", use_container_width=True):
                        set_selected_page(page)


def page_dashboard() -> None:
    st.title("Home / Dashboard")
    username, role = current_user()
    render_role_workbench(role)
    metrics = svc.dashboard_metrics(role, username)
    metric_grid(metrics)

    st.subheader("My dashboard overview")
    data = svc.chart_data(role, username)
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
    tasks = svc.get_dashboard_tasks(role, username, open_only=True)
    safe_df(tasks[[c for c in ["task_id", "reference_id", "euc_name", "task_type", "title", "assigned_to", "assigned_email", "due_date", "priority", "status", "overdue"] if c in tasks.columns]], height=260)


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
    show_cols = ["euc_id", "reference_id", "name", "legal_entity", "business_unit", "owner", "reviewer", "technology_type", "supports_material_report", "supports_material_kri", "supports_material_model", "last_risk_assessment_date", "inherent_risk", "residual_risk", "lifecycle_status", "documentation_completeness_status", "spof_indicator", "next_review_date"]
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
    if role != svc.OWNER_ROLE:
        st.warning("Registration is restricted to EUC Owners. Delegates can assist with assigned EUCs after registration. Group IT Governance Administrator manages the platform/configuration, not EUC registry content.")
        return
    if not require_write_access():
        return

    with st.form("register_euc"):
        st.subheader("Core EUC inventory information")
        c1, c2 = st.columns(2)
        name = c1.text_input("EUC Application Name *")
        legal_entity = reference_selectbox("legal_entity", "Legal Entity *", LEGAL_ENTITIES, key="register_legal_entity")
        business_unit = reference_selectbox("business_unit", "Business Unit *", BUSINESS_UNITS, key="register_business_unit")
        owner = user_selectbox("Owner *", username if role == svc.OWNER_ROLE else None, key="register_owner")
        owner_delegate = user_selectbox("Owner delegate / contributor", None, key="register_delegate", include_blank=True, role=svc.CONTRIBUTOR_ROLE)
        reviewer = user_selectbox("Reviewer", None, key="register_reviewer", include_blank=True)
        technology_type = c1.selectbox("Technology type *", TECHNOLOGY_TYPES)
        storage_location = c2.text_input("Storage location *", value="//eurobank/euc/")
        description = st.text_area(
            "Description",
            help="Briefly describe what the EUC is: file, tool, workflow, script, workbook, report, or process.",
        )
        purpose = st.text_area(
            "Purpose",
            help="Describe what the EUC is used for and what output it produces or supports.",
        )

        st.subheader("BCBS 239 scope indicators")
        r1, r2, r3 = st.columns(3)
        with r1:
            supports_material_report = bcbs_material_selectbox(
                "Supports Material Report in scope under Policy 241?",
                "Material Report",
                key="register_supports_report",
            )
        with r2:
            supports_material_kri = bcbs_material_selectbox(
                "Supports Material KRI in scope under Policy 241?",
                "Material KRI",
                key="register_supports_kri",
            )
        with r3:
            supports_material_model = bcbs_material_selectbox(
                "Supports Material Model in scope under Policy 241?",
                "Material Model",
                key="register_supports_model",
            )

        st.subheader("Usage and sourcing")
        u1, u2, u3 = st.columns(3)
        multi_bu_use = u1.selectbox("In use by two or more distinct BUs?", ["No", "Yes"], key="register_multi_bu")
        active_user_count = u2.number_input("Number of Active Users", min_value=0, step=1, value=1)
        created_by_bu = u3.selectbox("Created by the BU?", ["Yes", "No"], key="register_created_by_bu")
        s1, s2 = st.columns(2)
        acquired_third_party_cots = s1.selectbox("Acquired by third-party / COTS?", ["No", "Yes"], key="register_cots")
        support_contract_sla = s2.selectbox("Support contract / SLA in place?", ["No", "Yes", "Not Applicable"], key="register_sla")

        st.subheader("Mapping and operating context")
        c3, c4, c5 = st.columns(3)
        frequency = c3.selectbox("Frequency", FREQUENCIES, help="How often the EUC is executed, such as weekly, monthly, quarterly or ad hoc.")
        with c4:
            schedule = working_day_selectbox(
                "Execution schedule (working day)",
                help="Business working day on which the EUC should normally be executed, e.g. Working day 8.",
                key="register_execution_schedule_wd",
            )
        with c5:
            cut_off = working_day_selectbox(
                "Cut-off / delivery working day",
                help="Latest business working day by which the input, execution or output delivery must be completed.",
                key="register_cutoff_wd",
            )
        business_context = st.text_area(
            "Business / reporting context",
            help="Explain why this EUC matters in the business or reporting process, including downstream reports, decisions, controls or BCBS 239 relevance.",
        )
        default_mapping = supports_material_report if supports_material_report != "Not Applicable" else None
        bcbs_mapping = bcbs_output_selectbox("Primary BCBS 239 output mapping *", default_mapping, key="register_bcbs239_output")
        cde_linkage = st.text_area("CDE linkage (optional)")
        inputs = st.text_area("Inputs")
        outputs = st.text_area("Outputs")
        recipients = st.text_area("Recipients")
        dependencies = st.text_area("Dependencies")
        spof = st.radio("SPOF indicator", ["No", "Yes"], horizontal=True)
        mapping_na_justification = st.text_area("Not Applicable justification", help="Required if any mapping field is 'Not Applicable'.")
        lifecycle_status = st.selectbox("Initial lifecycle status", ["Draft", "Submitted", "Registered"], index=2)
        next_review_date = st.date_input("Next Risk Assessment / review date", value=date.today() + timedelta(days=90))
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
                    "business_context": business_context,
                    "supports_material_report": supports_material_report,
                    "supports_material_kri": supports_material_kri,
                    "supports_material_model": supports_material_model,
                    "multi_bu_use": multi_bu_use,
                    "active_user_count": int(active_user_count),
                    "created_by_bu": created_by_bu,
                    "acquired_third_party_cots": acquired_third_party_cots,
                    "support_contract_sla": support_contract_sla,
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
        record_table(
            euc,
            [
                "purpose",
                ("Legal Entity", "legal_entity"),
                "business_unit",
                "owner",
                "owner_delegate",
                "reviewer",
                "technology_type",
                "storage_location",
                "frequency",
                ("Execution schedule (working day)", "schedule"),
                ("Cut-off / delivery working day", "cut_off"),
                ("Used by two or more BUs", "multi_bu_use"),
                ("Number of Active Users", "active_user_count"),
                ("Created by BU", "created_by_bu"),
                ("Third-party / COTS", "acquired_third_party_cots"),
                ("Support contract / SLA", "support_contract_sla"),
                ("SPOF indicator", "spof_indicator"),
                ("Last Risk Assessment", "last_risk_assessment_date"),
                "next_review_date",
                "inherent_risk",
                "residual_risk",
            ],
            title="EUC summary",
        )
        if svc.can_edit_euc(role, username, euc):
            with st.expander("Edit EUC summary and lifecycle"):
                with st.form("edit_euc"):
                    name = st.text_input("EUC Application Name", value=euc.get("name") or "")
                    legal_entity = reference_selectbox("legal_entity", "Legal Entity", LEGAL_ENTITIES, euc.get("legal_entity"), key=f"edit_legal_entity_{euc['euc_id']}")
                    owner = user_selectbox("Owner", euc.get("owner"), key=f"edit_owner_{euc['euc_id']}")
                    delegate = user_selectbox("Owner delegate", euc.get("owner_delegate"), key=f"edit_delegate_{euc['euc_id']}", include_blank=True, role=svc.CONTRIBUTOR_ROLE)
                    reviewer = user_selectbox("Reviewer", euc.get("reviewer"), key=f"edit_reviewer_{euc['euc_id']}", include_blank=True)
                    unit = reference_selectbox("business_unit", "Business Unit", BUSINESS_UNITS, euc.get("business_unit"), key=f"edit_business_unit_{euc['euc_id']}")
                    tech = st.selectbox("Technology", TECHNOLOGY_TYPES, index=option_index(TECHNOLOGY_TYPES, euc.get("technology_type")))
                    storage = st.text_input("Storage location", value=euc.get("storage_location") or "")
                    lifecycle = st.selectbox("Lifecycle status", LIFECYCLE_STATUSES, index=option_index(LIFECYCLE_STATUSES, euc.get("lifecycle_status")))
                    overall = st.selectbox("Overall status", OVERALL_STATUSES, index=option_index(OVERALL_STATUSES, euc.get("overall_status")))
                    next_review = st.date_input("Next Risk Assessment / review date", value=pd.to_datetime(euc.get("next_review_date") or date.today()).date())
                    u1, u2, u3 = st.columns(3)
                    multi_bu_use = u1.selectbox("In use by two or more distinct BUs?", ["No", "Yes"], index=option_index(["No", "Yes"], euc.get("multi_bu_use") or "No"), key=f"edit_multi_bu_{euc['euc_id']}")
                    active_user_count = u2.number_input("Number of Active Users", min_value=0, step=1, value=int(euc.get("active_user_count") or 0), key=f"edit_active_users_{euc['euc_id']}")
                    created_by_bu = u3.selectbox("Created by the BU?", ["Yes", "No"], index=option_index(["Yes", "No"], euc.get("created_by_bu") or "Yes"), key=f"edit_created_by_bu_{euc['euc_id']}")
                    s1, s2 = st.columns(2)
                    acquired_third_party_cots = s1.selectbox("Acquired by third-party / COTS?", ["No", "Yes"], index=option_index(["No", "Yes"], euc.get("acquired_third_party_cots") or "No"), key=f"edit_cots_{euc['euc_id']}")
                    support_contract_sla = s2.selectbox("Support contract / SLA in place?", ["No", "Yes", "Not Applicable"], index=option_index(["No", "Yes", "Not Applicable"], euc.get("support_contract_sla") or "No"), key=f"edit_sla_{euc['euc_id']}")
                    c_sched1, c_sched2, c_sched3 = st.columns(3)
                    frequency = c_sched1.selectbox("Frequency", FREQUENCIES, index=option_index(FREQUENCIES, euc.get("frequency")), help="How often the EUC is executed.")
                    with c_sched2:
                        schedule = working_day_selectbox(
                            "Execution schedule (working day)",
                            euc.get("schedule"),
                            key=f"edit_execution_schedule_wd_{euc['euc_id']}",
                            help="Business working day on which the EUC should normally be executed.",
                        )
                    with c_sched3:
                        cut_off = working_day_selectbox(
                            "Cut-off / delivery working day",
                            euc.get("cut_off"),
                            key=f"edit_cutoff_wd_{euc['euc_id']}",
                            help="Latest business working day by which the EUC input, execution or output delivery must be completed.",
                        )
                    description = st.text_area(
                        "Description",
                        value=euc.get("description") or "",
                        help="Briefly describe what the EUC is: file, tool, workflow, script, workbook, report, or process.",
                    )
                    purpose = st.text_area(
                        "Purpose",
                        value=euc.get("purpose") or "",
                        help="Describe what the EUC is used for and what output it produces or supports.",
                    )
                    if st.form_submit_button("Save changes"):
                        payload = dict(euc)
                        payload.update({
                            "name": name,
                            "legal_entity": legal_entity,
                            "owner": owner,
                            "owner_delegate": delegate,
                            "reviewer": reviewer,
                            "business_unit": unit,
                            "technology_type": tech,
                            "storage_location": storage,
                            "lifecycle_status": lifecycle,
                            "overall_status": overall,
                            "next_review_date": next_review.isoformat(),
                            "frequency": frequency,
                            "schedule": schedule,
                            "cut_off": cut_off,
                            "multi_bu_use": multi_bu_use,
                            "active_user_count": int(active_user_count),
                            "created_by_bu": created_by_bu,
                            "acquired_third_party_cots": acquired_third_party_cots,
                            "support_contract_sla": support_contract_sla,
                            "description": description,
                            "purpose": purpose,
                        })
                        try:
                            svc.update_euc(euc["euc_id"], payload, username)
                            st.success("EUC updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    with tabs[1]:
        record_table(
            euc,
            [
                ("Business / reporting context", "business_context"),
                ("Supports Material Report", "supports_material_report"),
                ("Supports Material KRI", "supports_material_kri"),
                ("Supports Material Model", "supports_material_model"),
                ("BCBS 239 output mapping", "bcbs239_output_mapping"),
                ("CDE linkage", "cde_linkage"),
                "inputs",
                "outputs",
                "recipients",
                "dependencies",
                ("Not Applicable justification", "mapping_na_justification"),
            ],
            title="Mapping information",
        )
        if svc.can_edit_euc(role, username, euc):
            with st.expander("Edit mapping fields"):
                with st.form("edit_mapping"):
                    payload = dict(euc)
                    payload["business_context"] = st.text_area(
                        "Business / reporting context",
                        value=euc.get("business_context") or "",
                        help="Explain why this EUC matters in the business or reporting process, including downstream reports, decisions, controls or BCBS 239 relevance.",
                    )
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        payload["supports_material_report"] = bcbs_material_selectbox("Supports Material Report", "Material Report", euc.get("supports_material_report"), key="detail_supports_report")
                    with m2:
                        payload["supports_material_kri"] = bcbs_material_selectbox("Supports Material KRI", "Material KRI", euc.get("supports_material_kri"), key="detail_supports_kri")
                    with m3:
                        payload["supports_material_model"] = bcbs_material_selectbox("Supports Material Model", "Material Model", euc.get("supports_material_model"), key="detail_supports_model")
                    payload["bcbs239_output_mapping"] = bcbs_output_selectbox("Primary BCBS 239 output mapping *", euc.get("bcbs239_output_mapping"), key="detail_bcbs239_output")
                    for field in ["cde_linkage", "inputs", "outputs", "recipients", "dependencies", "mapping_na_justification"]:
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
        docs = svc.get_documents(euc["euc_id"])
        safe_df(docs)
        render_document_open_links(docs, "Open uploaded documentation")
    with tabs[5]:
        tasks = svc.get_tasks(open_only=False)
        if not tasks.empty:
            tasks = tasks[tasks["euc_id"] == euc["euc_id"]]
        safe_df(tasks)
    with tabs[6]:
        safe_df(svc.get_reviews(euc["euc_id"]))
    with tabs[7]:
        safe_df(svc.audit_trail({"entity_type": "EUC", "entity_id": euc["euc_id"]}), height=350)


def _component_asset_form(prefix: str, euc: dict[str, Any], component: dict[str, Any] | None = None) -> dict[str, Any]:
    component = component or {}
    record_table(
        euc,
        [
            ("Parent EUC reference", "reference_id"),
            ("EUC Application", "name"),
            ("Business Unit", "business_unit"),
            ("Owner", "owner"),
        ],
        title="Parent EUC context",
    )

    st.markdown("#### 1. Asset / file identification")
    c1, c2 = st.columns(2)
    component_name = c1.text_input("Files / Asset Name *", value=component.get("component_name") or "", key=f"{prefix}_component_name")
    file_description = c2.text_input("File description", value=component.get("file_description") or component.get("description") or "", key=f"{prefix}_file_description")
    description = st.text_area("Additional asset description / notes", value=component.get("description") or "", key=f"{prefix}_description")

    st.markdown("#### 2. Mapping and operationalization")
    c3, c4 = st.columns(2)
    with c3:
        rrf_mapping = bcbs_any_mapping_selectbox(
            "RRF Material Report / KRI / Model Mapping",
            component.get("rrf_mapping"),
            key=f"{prefix}_rrf_mapping",
        )
    operationalization_document_link = c4.text_input(
        "Operationalization Document Link",
        value=component.get("operationalization_document_link") or "",
        key=f"{prefix}_op_doc_link",
    )

    st.markdown("#### 3. Technology and controlled storage")
    c5, c6, c7 = st.columns(3)
    technology_type = c5.selectbox("Technology Type", TECHNOLOGY_TYPES, index=option_index(TECHNOLOGY_TYPES, component.get("technology_type") or component.get("component_type") or euc.get("technology_type")), key=f"{prefix}_technology_type")
    component_type = technology_type
    technology = c6.text_input("Technology details", value=component.get("technology") or technology_type or "", key=f"{prefix}_technology")
    controlled_storage_type = reference_selectbox("controlled_storage_type", "Controlled Storage Type", CONTROLLED_STORAGE_TYPES, component.get("controlled_storage_type"), key=f"{prefix}_controlled_storage_type")
    controlled_storage_location = st.text_input("Controlled Storage Location", value=component.get("controlled_storage_location") or component.get("storage_location") or euc.get("storage_location") or "", key=f"{prefix}_controlled_storage_location")

    st.markdown("#### 4. Inputs, outputs and CDEs")
    input_sources = st.text_area("Input sources", value=component.get("input_sources") or "", key=f"{prefix}_input_sources")
    cde_mappings = st.text_area("CDE Mappings", value=component.get("cde_mappings") or "", key=f"{prefix}_cde_mappings")
    data_outputs = st.text_area("Data Outputs", value=component.get("data_outputs") or "", key=f"{prefix}_data_outputs")

    st.markdown("#### 5. Schedule, frequency and cut-off")
    c8, c9, c10 = st.columns(3)
    with c8:
        asset_cut_off = working_day_selectbox("Cut-off working day", component.get("asset_cut_off") or euc.get("cut_off"), key=f"{prefix}_asset_cutoff")
    with c9:
        processing_schedule = working_day_selectbox("Processing Schedule / Execution Window", component.get("processing_schedule") or euc.get("schedule"), key=f"{prefix}_processing_schedule")
    execution_frequency = c10.selectbox("Execution Frequency", FREQUENCIES, index=option_index(FREQUENCIES, component.get("execution_frequency") or euc.get("frequency")), key=f"{prefix}_execution_frequency")

    st.markdown("#### 6. Automation, resilience and SPOF")
    c11, c12, c13 = st.columns(3)
    level_of_automation = reference_selectbox("level_of_automation", "Level of Automation", LEVELS_OF_AUTOMATION, component.get("level_of_automation"), key=f"{prefix}_automation")
    backup_recovery_arrangements = c12.text_input("Backup / Recovery Arrangements", value=component.get("backup_recovery_arrangements") or "", key=f"{prefix}_backup")
    spof_risk = c13.selectbox("Single Point of Failure risk", ["No", "Yes"], index=option_index(["No", "Yes"], component.get("spof_risk") or "No"), key=f"{prefix}_spof")

    st.markdown("#### 7. Ownership, criticality and review")
    c14, c15, c16, c17 = st.columns(4)
    owner_value = user_selectbox("Asset owner", component.get("owner") or euc.get("owner"), key=f"{prefix}_owner")
    criticality = c15.selectbox("Criticality", ["Low", "Medium", "High", "Critical"], index=option_index(["Low", "Medium", "High", "Critical"], component.get("criticality") or "Medium"), key=f"{prefix}_criticality")
    mod_default = pd.to_datetime(component.get("modification_date"), errors="coerce")
    review_default = pd.to_datetime(component.get("review_date"), errors="coerce")
    modification_date = c16.date_input("Modification Date", value=(mod_default.date() if pd.notna(mod_default) else date.today()), key=f"{prefix}_mod_date")
    review_date = c17.date_input("Review Date", value=(review_default.date() if pd.notna(review_default) else date.today() + timedelta(days=90)), key=f"{prefix}_review_date")

    return {
        "euc_id": euc["euc_id"],
        "component_name": component_name.strip(),
        "component_type": component_type,
        "technology": technology,
        "storage_location": controlled_storage_location,
        "description": description,
        "criticality": criticality,
        "owner": owner_value,
        "rrf_mapping": rrf_mapping,
        "operationalization_document_link": operationalization_document_link,
        "file_description": file_description,
        "technology_type": technology_type,
        "controlled_storage_type": controlled_storage_type,
        "controlled_storage_location": controlled_storage_location,
        "input_sources": input_sources,
        "asset_cut_off": asset_cut_off,
        "processing_schedule": processing_schedule,
        "execution_frequency": execution_frequency,
        "cde_mappings": cde_mappings,
        "data_outputs": data_outputs,
        "level_of_automation": level_of_automation,
        "backup_recovery_arrangements": backup_recovery_arrangements,
        "spof_risk": spof_risk,
        "modification_date": modification_date.isoformat(),
        "review_date": review_date.isoformat(),
    }


def page_components() -> None:
    st.title("Components / EUC Asset Inventory")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return

    components = svc.get_components(euc["euc_id"])
    st.subheader(f"EUC Asset Inventory for {euc['reference_id']} — {euc['name']}")
    st.caption("Each asset row is linked to the parent EUC through euc_id. Parent Business Unit and EUC Application are shown from the EUC Inventory record and are not typed manually in the child asset form.")
    safe_df(components, height=380)

    can_edit = svc.can_edit_euc(role, username, euc) or role == svc.GCC_ROLE
    if not can_edit:
        st.info("You can view components/assets but cannot add or edit them for this EUC in the current role.")
        return

    tabs = st.tabs(["Edit selected asset", "Add asset"])
    with tabs[0]:
        if components.empty:
            st.info("No assets exist for this EUC yet.")
        else:
            component_map = {
                f"{row['component_id']} — {row['component_name']} — {row.get('technology_type') or row.get('component_type')}": int(row["component_id"])
                for _, row in components.iterrows()
            }
            chosen = st.selectbox("Select asset to edit", list(component_map.keys()))
            component = svc.get_component(component_map[chosen])
            if component:
                with st.form("edit_component"):
                    payload = _component_asset_form(f"edit_component_{component['component_id']}", euc, component)
                    if st.form_submit_button("Save asset changes", type="primary"):
                        try:
                            svc.update_component(int(component["component_id"]), payload, username)
                            st.success("Asset updated.")
                            rerun()
                        except ValueError as exc:
                            st.error(str(exc))

    with tabs[1]:
        with st.form("add_component"):
            st.subheader("Add asset")
            payload = _component_asset_form(f"add_component_{euc['euc_id']}", euc, None)
            if st.form_submit_button("Add asset", type="primary"):
                try:
                    svc.create_component(payload, username)
                    st.success("Asset added.")
                    rerun()
                except ValueError as exc:
                    st.error(str(exc))

def page_risk_assessment() -> None:
    st.title("Risk Assessment")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return

    st.caption("Excel-aligned model: BCBS 239 materiality forces effective inherent risk to Very High; residual risk follows the workbook control-effectiveness matrix.")
    assessments = svc.get_risk_assessments(euc["euc_id"])
    safe_df(assessments, height=260)

    can_owner_edit = svc.can_edit_euc(role, username, euc)
    can_assessment_review = svc.risk_assessment_edit_can_be_approved_by(role)

    if not assessments.empty:
        with st.expander("Open completed assessment for review", expanded=False):
            assessment_map = {
                f"Assessment {row['assessment_id']} — version {row['version']} — status {row.get('status', 'Submitted')} — residual {row.get('overall_residual_risk') or row.get('residual_risk')}": int(row["assessment_id"])
                for _, row in assessments.iterrows()
            }
            chosen = st.selectbox("Completed assessment", list(assessment_map.keys()), key="risk_review_select")
            selected = assessments[assessments["assessment_id"] == assessment_map[chosen]].iloc[0].to_dict()
            assessment_review_card(selected)
            st.info("Completed assessments can be amended in place only after GCC or Data Validation approves an edit request. Otherwise, submit a new assessment version for a new trigger/event.")

        if can_assessment_review and require_write_access():
            with st.expander("Reviewer decision", expanded=False):
                review_map = {
                    f"#{row['assessment_id']} — version {row['version']} — {row.get('status', 'Submitted')}": int(row["assessment_id"])
                    for _, row in assessments.iterrows()
                }
                chosen_review = st.selectbox("Assessment to review", list(review_map.keys()), key="risk_assessment_review_select")
                current = assessments[assessments["assessment_id"] == review_map[chosen_review]].iloc[0].to_dict()
                with st.form("review_risk_assessment"):
                    status = st.selectbox(
                        "Review status",
                        ["Submitted", "Accepted", "Rejected"],
                        index=option_index(["Submitted", "Accepted", "Rejected"], current.get("status") or "Submitted"),
                    )
                    comments = st.text_area("Review comments", value=current.get("review_comments") or "")
                    if st.form_submit_button("Save risk assessment review"):
                        svc.review_risk_assessment(review_map[chosen_review], status, comments, username)
                        st.success("Risk assessment review status updated.")
                        rerun()

        st.subheader("Risk assessment amendment workflow")
        if can_owner_edit and require_write_access():
            request_map = {
                f"#{row['assessment_id']} — version {row['version']} — edit request: {row.get('edit_request_status') or 'Not Requested'}": int(row["assessment_id"])
                for _, row in assessments.iterrows()
            }
            chosen_request = st.selectbox("Assessment to amend", list(request_map.keys()), key="risk_edit_request_select")
            selected_request = assessments[assessments["assessment_id"] == request_map[chosen_request]].iloc[0].to_dict()
            current_request_status = selected_request.get("edit_request_status") or "Not Requested"
            st.caption(f"Current edit-request status: **{current_request_status}**")
            if current_request_status != "Approved":
                with st.form("request_assessment_edit"):
                    reason = st.text_area("Why is an amendment needed?", value=selected_request.get("edit_request_reason") or "")
                    if st.form_submit_button("Request edit approval"):
                        if not reason.strip():
                            st.error("Provide the reason for the amendment request.")
                        else:
                            svc.request_risk_assessment_edit(request_map[chosen_request], reason.strip(), username)
                            st.success("Edit request submitted to GCC / Data Validation.")
                            rerun()
            else:
                st.info("The edit request is approved. You can amend this assessment in place below. Saving will reset the assessment status to Submitted for review.")
                edit_payload = risk_assessment_input_form(
                    "edit_risk_assessment_in_place",
                    euc,
                    username,
                    defaults=selected_request,
                    submit_label="Save amendment and resubmit",
                )
                if edit_payload:
                    svc.update_risk_assessment_in_place(request_map[chosen_request], edit_payload, username)
                    st.success("Risk assessment amended in place and resubmitted for review.")
                    rerun()
        elif can_assessment_review and require_write_access():
            pending = assessments[assessments.get("edit_request_status", pd.Series(dtype=str)).fillna("Not Requested") == "Pending"]
            if pending.empty:
                st.info("No risk assessment edit requests are pending.")
            else:
                decision_map = {
                    f"#{row['assessment_id']} — version {row['version']} — requested by {row.get('edit_requested_by') or '-'}": int(row["assessment_id"])
                    for _, row in pending.iterrows()
                }
                chosen_decision = st.selectbox("Pending edit request", list(decision_map.keys()), key="risk_edit_decision_select")
                selected_pending = pending[pending["assessment_id"] == decision_map[chosen_decision]].iloc[0].to_dict()
                record_table(
                    selected_pending,
                    [
                        ("Requested by", "edit_requested_by"),
                        ("Requested at", "edit_requested_at"),
                        ("Reason", "edit_request_reason"),
                    ],
                    title="Request details",
                )
                with st.form("decide_assessment_edit"):
                    decision = st.selectbox("Decision", ["Approved", "Rejected"])
                    comments = st.text_area("Decision comments")
                    if st.form_submit_button("Save edit-request decision"):
                        svc.decide_risk_assessment_edit_request(decision_map[chosen_decision], decision, comments, username)
                        st.success("Risk assessment edit-request decision saved.")
                        rerun()

    if role == svc.ADMIN_ROLE:
        st.info("Group IT Governance Administrator can configure the platform, but does not create, amend, approve, or reject EUC risk assessments.")
        return

    if not can_owner_edit:
        st.warning("Only the EUC Owner or delegated contributor can submit a risk assessment. GCC and Data Validation review or approve amendment requests.")
        return

    st.subheader("Submit new risk assessment version")
    st.caption("Use this for onboarding, periodic review, incident-triggered reassessment, or material-change reassessment. To correct an existing assessment, use the amendment workflow above after approval.")
    payload = risk_assessment_input_form("risk_assessment_excel", euc, username, defaults=None, submit_label="Submit new assessment version")
    if payload:
        calculated = svc.calculate_excel_risk_assessment(payload)
        payload["status"] = "Submitted"
        assessment_id = svc.create_risk_assessment(payload, username)
        st.success(f"Assessment {assessment_id} submitted for review. Overall inherent risk: {calculated['overall_inherent_risk']}; overall residual risk: {calculated['overall_residual_risk']}.")
        st.info(calculated["required_action"])
        rerun()

def page_documents() -> None:
    st.title("Documents & Evidence Pack")
    username, role = current_user()
    euc = euc_selector()
    if not euc:
        return

    st.subheader("Required artifact checklist")
    baseline = svc.inherent_baseline_for_euc(euc["euc_id"])
    st.caption(
        f"Required artifacts are driven by the policy baseline: **{baseline['baseline_risk']} Overall Inherent Risk** "
        f"({baseline['source']}). Residual risk drives remediation, escalation and exceptions; it does not reduce the baseline evidence pack."
    )
    # Synchronize documentation completeness/lifecycle before showing the checklist.
    svc.evaluate_and_update_completeness(euc["euc_id"], username, create_missing_tasks=False)
    checklist = svc.artifact_checklist(euc["euc_id"])
    st.caption("Use the what_to_upload column to understand exactly what evidence is expected for each requirement. Filter directly inside the table using the column filter boxes.")
    safe_df(checklist, height=300, key=f"documents_required_artifacts_{euc['euc_id']}")

    st.subheader("Completed risk assessments used as internal evidence")
    assessments = svc.get_risk_assessments(euc["euc_id"])
    if assessments.empty:
        st.warning("No completed risk assessment exists for this EUC. Complete the Risk Assessment module; do not upload a separate risk assessment file.")
    else:
        assessment_cols = [
            col for col in [
                "assessment_id", "version", "assessment_date", "assessed_by", "materially_supports_bcbs239",
                "owner_integrity_inherent", "owner_timeliness_inherent", "effective_integrity_inherent",
                "effective_timeliness_inherent", "overall_inherent_risk", "overall_residual_risk", "required_action",
            ] if col in assessments.columns
        ]
        safe_df(assessments[assessment_cols], height=220)
        assessment_map = {
            f"Open assessment {row['assessment_id']} — version {row['version']}": int(row["assessment_id"])
            for _, row in assessments.iterrows()
        }
        chosen_assessment = st.selectbox("Risk assessment review link", list(assessment_map.keys()), key="evidence_assessment_link")
        if st.button("Open selected assessment for review"):
            st.session_state["evidence_open_assessment_id"] = assessment_map[chosen_assessment]
        open_id = st.session_state.get("evidence_open_assessment_id")
        if open_id:
            selected = assessments[assessments["assessment_id"] == int(open_id)]
            if not selected.empty:
                with st.expander(f"Assessment {open_id} review", expanded=True):
                    assessment_review_card(selected.iloc[0].to_dict())

    st.subheader("Uploaded evidence")
    docs = svc.get_documents(euc["euc_id"])
    safe_df(docs, height=300)
    render_document_open_links(docs, "Open uploaded documentation")

    col_upload, col_review = st.columns(2)
    uploadable_document_types = [doc for doc in DOCUMENT_TYPES if doc != "Risk Assessment"]
    with col_upload:
        st.subheader("Upload evidence")
        if svc.can_upload_evidence(role, username, euc) and require_write_access():
            # Use an EUC-specific nonce in widget and form keys so selected
            # artifact types, uploaded files and comments are cleared immediately
            # after a successful upload. File uploader widgets are only reliably
            # reset in Streamlit when their key changes.
            reset_key = f"doc_upload_reset_nonce_{euc['euc_id']}"
            st.session_state.setdefault(reset_key, 0)
            upload_nonce = st.session_state[reset_key]
            type_widget_key = f"doc_upload_types_{euc['euc_id']}_{upload_nonce}"
            file_widget_key = f"doc_upload_files_{euc['euc_id']}_{upload_nonce}"
            comments_widget_key = f"doc_upload_comments_{euc['euc_id']}_{upload_nonce}"
            upload_form_key = f"doc_metadata_{euc['euc_id']}_{upload_nonce}"

            last_msg_key = f"doc_upload_last_message_{euc['euc_id']}"
            if st.session_state.get(last_msg_key):
                st.success(st.session_state.pop(last_msg_key))

            selected_types = st.multiselect(
                "Document type(s) covered by the upload",
                uploadable_document_types,
                default=[],
                key=type_widget_key,
                help="Select one or more artifact types. A single uploaded file may cover multiple required artifact types; multiple files may also be uploaded for the same type.",
            )
            if selected_types:
                for doc_type in selected_types:
                    with st.expander(f"What to upload for {doc_type}", expanded=len(selected_types) == 1):
                        st.info(svc.artifact_upload_guidance(doc_type))
            else:
                st.info("Select at least one document type to see what evidence is expected.")

            uploaded_files = st.file_uploader(
                "Upload one or more document / evidence files",
                accept_multiple_files=True,
                key=file_widget_key,
                help="You may upload multiple documents for the same type. If one file covers several evidence types, select all applicable types above.",
            )
            if selected_types and uploaded_files:
                st.caption(
                    f"This submission will create **{len(selected_types) * len(uploaded_files)}** evidence record(s): "
                    f"{len(uploaded_files)} file(s) × {len(selected_types)} document type(s)."
                )

            clear_col, _ = st.columns([1, 2])
            with clear_col:
                if st.button("Clear selected files/types", key=f"clear_upload_selection_{euc['euc_id']}_{upload_nonce}"):
                    st.session_state[reset_key] += 1
                    rerun()

            with st.form(upload_form_key, clear_on_submit=False):
                comments = st.text_area("Comments", key=comments_widget_key)
                if st.form_submit_button("Save uploaded evidence"):
                    if not uploaded_files:
                        st.error("Select at least one file before saving evidence.")
                    elif not selected_types:
                        st.error("Select at least one document type covered by the uploaded file(s).")
                    else:
                        created_ids: list[int] = []
                        upload_summary: dict[str, list[str]] = {}
                        for uploaded in uploaded_files:
                            file_name, file_path = svc.save_document_file(euc["euc_id"], uploaded.name, uploaded.getvalue())
                            upload_summary[file_name] = list(selected_types)
                            for document_type in selected_types:
                                doc_id = svc.create_document_record(
                                    {
                                        "euc_id": euc["euc_id"],
                                        "file_name": file_name,
                                        "file_path": file_path,
                                        "document_type": document_type,
                                        "requirement": None,
                                        "control_area": None,
                                        "cacrt_dimension": None,
                                        "risk_applicability": None,
                                        "lifecycle_stage": None,
                                        "version": None,
                                        "status": "Submitted",
                                        "comments": comments,
                                    },
                                    username,
                                )
                                created_ids.append(doc_id)
                        summary_text = "; ".join(
                            f"{file_name} → {', '.join(types)}" for file_name, types in upload_summary.items()
                        )
                        st.session_state[last_msg_key] = (
                            f"Evidence uploaded. Created {len(created_ids)} evidence record(s): "
                            f"{', '.join(map(str, created_ids))}. {summary_text}"
                        )
                        # Rotate all upload widget keys and rerun. This clears the
                        # multi-select, file uploader and comments field after save.
                        st.session_state[reset_key] += 1
                        rerun()
        else:
            st.info("Upload is disabled for the current role/EUC relationship.")

    with col_review:
        st.subheader("Review evidence")
        if svc.can_review(role) and require_write_access() and not docs.empty:
            doc_map = {f"{row['document_id']} — {row['document_type']} — {row['status']}": int(row["document_id"]) for _, row in docs.iterrows()}
            chosen = st.selectbox("Document", list(doc_map.keys()))
            selected_doc = docs[docs["document_id"] == doc_map[chosen]].iloc[0].to_dict()
            render_document_open_links(pd.DataFrame([selected_doc]), "Open selected evidence before review")
            with st.form("review_doc"):
                status = st.selectbox("Review status", ["Accepted", "Rejected", "Expired", "Superseded", "Submitted"], index=option_index(["Accepted", "Rejected", "Expired", "Superseded", "Submitted"], selected_doc.get("status")))
                deficiency = st.text_input("Deficiency tag", value=selected_doc.get("deficiency_tag") or "", placeholder="e.g., missing sign-off, expired evidence")
                comments = st.text_area("Review comments", value=selected_doc.get("comments") or "")
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
    # The checklist is calculated, so sync the stored EUC documentation and lifecycle
    # status before displaying it. This prevents stale values such as
    # "Awaiting Documentation" after all mandatory artifacts have been accepted.
    svc.evaluate_and_update_completeness(euc["euc_id"], username, create_missing_tasks=False)
    euc = svc.get_euc(euc["euc_id"]) or euc
    baseline = svc.inherent_baseline_for_euc(euc["euc_id"])
    st.markdown(
        f"Inherent baseline: **{badge(baseline['baseline_risk'])}** · "
        f"Residual risk: **{badge(euc['residual_risk'])}** · "
        f"Lifecycle: **{badge(euc['lifecycle_status'])}** · "
        f"Documentation: **{badge(euc.get('documentation_completeness_status'))}**"
    )
    st.caption("Checklist baseline follows Overall Inherent Risk / BCBS 239 materiality. Residual risk is used for remediation, escalation and exception handling.")
    checklist = svc.artifact_checklist(euc["euc_id"])
    st.caption("Filter directly inside the table using the column filter boxes.")
    safe_df(checklist, height=350, key=f"standalone_required_artifacts_{euc['euc_id']}")
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
    st.caption(
        "This page is scoped to the logged-in user. It shows tasks assigned to you, "
        "tasks assigned to your role queue, and, for EUC owners/contributors, tasks linked to your own or delegated EUCs."
    )
    open_only = st.toggle("Open tasks only", value=True)
    scoped_tasks = svc.get_tasks(role, username, open_only=open_only)

    if scoped_tasks.empty:
        st.info("No tasks are assigned to your user, role queue, or accessible EUCs for the current filter.")
        return

    euc_options = ["All my accessible tasks"]
    euc_lookup: dict[str, int] = {}
    euc_cols = [c for c in ["euc_id", "reference_id", "euc_name"] if c in scoped_tasks.columns]
    if set(["euc_id", "reference_id", "euc_name"]).issubset(euc_cols):
        euc_rows = scoped_tasks[["euc_id", "reference_id", "euc_name"]].drop_duplicates().sort_values(["reference_id", "euc_name"])
        for _, row in euc_rows.iterrows():
            label = f"{row['reference_id']} — {row['euc_name']}"
            euc_options.append(label)
            euc_lookup[label] = int(row["euc_id"])

    chosen_euc = st.selectbox("Filter by EUC", euc_options)
    tasks = scoped_tasks.copy()
    if chosen_euc != "All my accessible tasks":
        tasks = tasks[tasks["euc_id"] == euc_lookup[chosen_euc]]

    display_cols = [
        "task_id", "reference_id", "euc_name", "task_type", "title", "assigned_to",
        "assigned_full_name", "assigned_email", "assigned_role", "due_date", "priority", "status", "overdue"
    ]
    safe_df(tasks[[c for c in display_cols if c in tasks.columns]], height=420)

    if tasks.empty or svc.is_read_only(role):
        return

    st.subheader("Update selected task")
    task_map = {f"{row['task_id']} — {row['title']}": int(row["task_id"]) for _, row in tasks.iterrows()}
    chosen = st.selectbox("Task", list(task_map.keys()))
    selected_task = tasks[tasks["task_id"] == task_map[chosen]].iloc[0].to_dict()
    with st.form("update_task"):
        c1, c2, c3 = st.columns(3)
        status = c1.selectbox("Status", TASK_STATUSES, index=option_index(TASK_STATUSES, selected_task.get("status")))
        priority = c2.selectbox("Priority", PRIORITIES, index=option_index(PRIORITIES, selected_task.get("priority")))
        due_default = pd.to_datetime(selected_task.get("due_date"), errors="coerce")
        due_date = c3.date_input("Due date", value=(due_default.date() if pd.notna(due_default) else date.today()))
        evidence_id = st.number_input(
            "Closure evidence document ID",
            min_value=0,
            value=int(selected_task.get("closure_evidence_document_id") or 0),
            step=1,
        )
        reason = st.text_area("Closure reason / response", value=selected_task.get("closure_reason") or "")
        if st.form_submit_button("Update task"):
            # The table is already scoped to the current user/role. Only selected
            # task IDs from that scoped table can be submitted through this form.
            svc.update_task(task_map[chosen], status, reason, int(evidence_id) or None, username)
            svc.update_task_admin_fields(task_map[chosen], due_date.isoformat(), priority, username)
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



def _reports_filter_controls(df: pd.DataFrame, key_prefix: str = "reports") -> dict[str, Any]:
    """Common filters for policy reports and custom report previews."""
    c1, c2, c3, c4 = st.columns(4)
    owners = ["All"] + sorted(df["owner"].dropna().astype(str).unique().tolist()) if df is not None and not df.empty and "owner" in df.columns else ["All"]
    units = ["All"] + sorted(df["business_unit"].dropna().astype(str).unique().tolist()) if df is not None and not df.empty and "business_unit" in df.columns else ["All"]
    owner = c1.selectbox("Owner", owners, key=f"{key_prefix}_owner")
    unit = c2.selectbox("Business unit", units, key=f"{key_prefix}_unit")
    inherent = c3.selectbox("Overall inherent risk", ["All"] + RISK_LEVELS, key=f"{key_prefix}_inherent")
    residual = c4.selectbox("Overall residual risk", ["All"] + RISK_LEVELS, key=f"{key_prefix}_residual")
    c5, c6 = st.columns(2)
    lifecycle = c5.selectbox("Lifecycle status", ["All"] + LIFECYCLE_STATUSES, key=f"{key_prefix}_lifecycle")
    output_mapping = c6.text_input("BCBS 239 output mapping contains", key=f"{key_prefix}_output")
    return {
        "owner": owner,
        "business_unit": unit,
        "inherent_risk": inherent,
        "residual_risk": residual,
        "lifecycle_status": lifecycle,
        "output_mapping": output_mapping,
    }


def page_reports() -> None:
    st.title("Reports & KPIs")
    username, role = current_user()
    if role not in REPORTS_ACCESS_ROLES:
        st.warning("Reports & KPIs are restricted to GCC, Data Validation Unit, and Group IT Governance Administrator users.")
        return

    st.caption(
        "Policy-ready MI pack based on the EUC Policy: inventory coverage and risk distribution, BCBS 239 output coverage, "
        "Library/CACRT KPIs, incidents, exceptions, remediation and industrialization pipeline. Custom reports can be saved below."
    )
    euc_df = svc.all_eucs()
    filters = _reports_filter_controls(euc_df, "policy_reports")

    tabs = st.tabs(["Policy KPI dashboard", "Policy report pack", "Custom reports"])

    with tabs[0]:
        st.subheader("Policy KPI dashboard")
        kpis = svc.policy_kpi_cards(filters)
        metric_items = list(kpis.items())
        for row_start in range(0, len(metric_items), 4):
            cols = st.columns(4)
            for col, (label, value) in zip(cols, metric_items[row_start:row_start + 4]):
                suffix = "%" if label.endswith("%") else ""
                col.metric(label, f"{value}{suffix}" if suffix else value)

        charts = svc.policy_report_charts(filters)
        c1, c2 = st.columns(2)
        if not charts["inherent_risk"].empty:
            c1.plotly_chart(px.bar(charts["inherent_risk"], x="risk_level", y="count", title="Overall inherent risk distribution"), use_container_width=True)
        if not charts["residual_risk"].empty:
            c2.plotly_chart(px.bar(charts["residual_risk"], x="risk_level", y="count", title="Overall residual risk distribution"), use_container_width=True)
        c3, c4 = st.columns(2)
        if not charts["lifecycle"].empty:
            c3.plotly_chart(px.bar(charts["lifecycle"], x="lifecycle_status", y="count", title="Lifecycle distribution"), use_container_width=True)
        if not charts["business_unit"].empty:
            c4.plotly_chart(px.bar(charts["business_unit"], x="business_unit", y="count", title="Area / business-unit segments"), use_container_width=True)

        st.markdown("#### Source report definitions")
        safe_df(pd.DataFrame(svc.policy_report_catalog()), height=320)

    with tabs[1]:
        st.subheader("Policy report pack")
        catalog = svc.policy_report_catalog()
        labels = {f"{item['name']}": item["key"] for item in catalog}
        selected_name = st.selectbox("Prepared policy report", list(labels.keys()))
        selected_key = labels[selected_name]
        meta = next(item for item in catalog if item["key"] == selected_key)
        st.info(meta["description"])
        st.caption(meta["policy_basis"])
        report_df = svc.run_policy_report(selected_key, filters)
        safe_df(report_df, height=520)
        csv_download(report_df, f"{selected_key}.csv")

    with tabs[2]:
        st.subheader("Custom reports")
        st.caption("Create reusable reports without writing SQL. Reports use approved app datasets and are visible to the Reports & KPIs roles.")
        existing = svc.custom_report_definitions_table(active_only=False)
        if not existing.empty:
            st.markdown("#### Saved custom reports")
            safe_df(existing, height=260)
            active_existing = existing[existing["active_flag"].astype(bool)] if "active_flag" in existing.columns else existing
            if not active_existing.empty:
                labels = {f"{row['report_name']} — {row['dataset']}": int(row["report_id"]) for _, row in active_existing.iterrows()}
                selected = st.selectbox("Run saved report", list(labels.keys()))
                if st.button("Run selected custom report"):
                    custom_df = svc.run_custom_report_definition(labels[selected])
                    st.session_state["last_custom_report_df"] = custom_df
                    st.session_state["last_custom_report_name"] = selected
                if "last_custom_report_df" in st.session_state:
                    st.markdown(f"#### Result: {st.session_state.get('last_custom_report_name', 'Custom report')}")
                    result = st.session_state["last_custom_report_df"]
                    safe_df(result, height=440)
                    csv_download(result, "custom_report.csv")

        st.markdown("#### Create or update a custom report")
        dataset = st.selectbox("Dataset", svc.custom_report_dataset_names(), key="custom_report_dataset")
        available_cols = svc.custom_report_dataset_columns(dataset)
        default_cols = available_cols[: min(10, len(available_cols))]
        with st.form("custom_report_builder"):
            c1, c2 = st.columns(2)
            report_name = c1.text_input("Report name *")
            active_flag = c2.checkbox("Active", value=True)
            description = st.text_area("Description")
            selected_columns = st.multiselect("Columns", available_cols, default=default_cols)
            st.markdown("##### Optional filters")
            filter_cols = st.multiselect("Filter columns", available_cols, help="For text filters, rows are retained when the cell contains the entered value.")
            filters_json: dict[str, str] = {}
            for col in filter_cols[:8]:
                filters_json[col] = st.text_input(f"Filter value for {col}")
            save_custom = st.form_submit_button("Save custom report", type="primary")
            if save_custom:
                if not report_name.strip():
                    st.error("Report name is required.")
                else:
                    svc.upsert_custom_report_definition(
                        {
                            "report_name": report_name.strip(),
                            "description": description.strip(),
                            "dataset": dataset,
                            "selected_columns": selected_columns,
                            "filters": filters_json,
                            "active_flag": active_flag,
                        },
                        username,
                    )
                    st.success("Custom report saved.")
                    rerun()


def page_admin() -> None:
    st.title("Admin Configuration")
    username, role = current_user()
    if not svc.can_configure(role):
        st.warning("Admin Configuration is restricted to Group IT Governance Administrator.")
        return
    refs = svc.load_reference_data()
    tabs = st.tabs(["Reference data", "User directory", "Required artifact rules", "Due-date rules", "BCBS 239 outputs", "Seed/reset demo"])
    with tabs[0]:
        category = st.selectbox(
            "Category",
            [
                "document_type",
                "lifecycle_status",
                "risk_level",
                "control_area",
                "cacrt_dimension",
                "legal_entity",
                "business_unit",
                "controlled_storage_type",
                "level_of_automation",
            ],
        )
        st.write("Current values")
        values_df = pd.DataFrame({"Value": refs.get(category, [])})
        safe_df(values_df)
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
        st.subheader("User directory")
        st.caption("Select a user row in the table to load it into the edit form. Seeded demo users start with ekassotis@eurobank.gr, but the email address remains editable for future routing changes.")
        users_df = svc.user_profiles_table(active_only=False)
        selected_user = None
        if users_df.empty:
            st.info("No users have been configured yet.")
        else:
            selected_rows = selectable_df(users_df, key="user_directory_table", height=360)
            labels = {f"{row['username']} — {row['role']}": int(row["user_id"]) for _, row in users_df.iterrows()}
            fallback_label = st.selectbox("Selected user", list(labels.keys()), key="user_directory_selectbox")
            fallback_id = labels[fallback_label]
            selected_id = int(selected_rows[0].get("user_id")) if selected_rows and selected_rows[0].get("user_id") is not None else fallback_id
            selected_user = svc.get_user_profile(selected_id)

        if selected_user:
            st.markdown("#### Edit selected user")
            with st.form("edit_user_profile"):
                c1, c2 = st.columns(2)
                edit_username = c1.text_input("Username *", value=selected_user.get("username") or "")
                full_name = c2.text_input("Full name", value=selected_user.get("full_name") or "")
                email = c1.text_input("Email", value=selected_user.get("email") or svc.DEFAULT_EMAIL_ADDRESS)
                edit_role = c2.selectbox("Role *", DIRECTORY_ROLES, index=option_index(DIRECTORY_ROLES, selected_user.get("role")))
                active = c1.checkbox("Active", value=bool(selected_user.get("active_flag")))
                comments = st.text_area("Maker-checker / admin comments", value=selected_user.get("maker_checker_comments") or "")
                save_user = st.form_submit_button("Save selected user", type="primary")
                if save_user:
                    if not edit_username.strip():
                        st.error("Username is required.")
                    else:
                        svc.update_user_profile(
                            int(selected_user["user_id"]),
                            {
                                "username": edit_username.strip(),
                                "full_name": full_name.strip(),
                                "email": email.strip() or svc.DEFAULT_EMAIL_ADDRESS,
                                "role": edit_role,
                                "active_flag": active,
                                "maker_checker_comments": comments,
                            },
                            username,
                        )
                        st.success("User profile updated.")
                        rerun()

        with st.expander("Add new user"):
            with st.form("add_user_profile"):
                c1, c2 = st.columns(2)
                new_username = c1.text_input("New username *")
                new_full_name = c2.text_input("New full name")
                new_email = c1.text_input("New email", value=svc.DEFAULT_EMAIL_ADDRESS)
                new_role = c2.selectbox("New role *", DIRECTORY_ROLES, key="new_user_role")
                new_active = c1.checkbox("New user active", value=True)
                new_comments = st.text_area("New user comments")
                if st.form_submit_button("Create user"):
                    if not new_username.strip():
                        st.error("Username is required.")
                    else:
                        svc.upsert_user_profile(
                            {
                                "username": new_username.strip(),
                                "full_name": new_full_name.strip(),
                                "email": new_email.strip() or svc.DEFAULT_EMAIL_ADDRESS,
                                "role": new_role,
                                "active_flag": new_active,
                                "maker_checker_comments": new_comments,
                            },
                            username,
                        )
                        st.success("User profile created.")
                        rerun()
    with tabs[2]:
        safe_df(svc.required_rules_table(), height=320)
        with st.form("add_rule"):
            c1, c2, c3 = st.columns(3)
            risk = c1.selectbox("Overall inherent risk baseline", RISK_LEVELS)
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
    with tabs[3]:
        safe_df(svc.due_date_rules_table(), height=360)
        st.caption("Due-date rule editing is represented in the data model. The MVP uses default seeded rules for generated tasks.")
    with tabs[4]:
        st.subheader("BCBS 239 mapping outputs")
        st.caption("These values feed the controlled BCBS 239 output mapping combo box used during EUC registration and mapping edits. Seeded values come from Detailed Inventory, column D, of the BCBS 239 material reports workbook.")
        outputs_df = svc.bcbs239_outputs_table(active_only=False)
        safe_df(outputs_df, height=360)
        if not outputs_df.empty:
            labels = {f"{row['output_id']} — {row['output_name']}": int(row["output_id"]) for _, row in outputs_df.iterrows()}
            selected_label = st.selectbox("Select output to edit", list(labels.keys()), key="bcbs_output_select")
            selected_output = outputs_df[outputs_df["output_id"] == labels[selected_label]].iloc[0].to_dict()
            with st.form("edit_bcbs_output"):
                c1, c2 = st.columns(2)
                out_name = c1.text_input("Output / report name *", value=selected_output.get("output_name") or "")
                out_type = c2.selectbox("Output type", BCBS239_OUTPUT_TYPES, index=option_index(BCBS239_OUTPUT_TYPES, selected_output.get("output_type") or "Material Report"))
                out_owner = c1.text_input("Owner", value=selected_output.get("owner") or "")
                out_active = c2.checkbox("Active", value=bool(selected_output.get("active_flag")))
                out_comments = st.text_area("Maker-checker comments", value=selected_output.get("maker_checker_comments") or "")
                if st.form_submit_button("Save selected output", type="primary"):
                    svc.upsert_bcbs239_output(
                        {
                            "output_name": out_name.strip(),
                            "output_type": out_type or "Material Report",
                            "owner": out_owner.strip(),
                            "active_flag": out_active,
                            "maker_checker_comments": out_comments,
                        },
                        username,
                    )
                    st.success("BCBS 239 output updated.")
                    rerun()
        with st.expander("Add new BCBS 239 output"):
            with st.form("add_bcbs_output"):
                c1, c2 = st.columns(2)
                new_out_name = c1.text_input("New output / report name *")
                new_out_type = c2.selectbox("New output type", BCBS239_OUTPUT_TYPES, index=0)
                new_out_owner = c1.text_input("New owner")
                new_out_active = c2.checkbox("New output active", value=True)
                new_out_comments = st.text_area("New output comments")
                if st.form_submit_button("Create BCBS 239 output"):
                    if not new_out_name.strip():
                        st.error("Output name is required.")
                    else:
                        svc.upsert_bcbs239_output(
                            {
                                "output_name": new_out_name.strip(),
                                "output_type": new_out_type or "Material Report",
                                "owner": new_out_owner.strip(),
                                "active_flag": new_out_active,
                                "maker_checker_comments": new_out_comments,
                            },
                            username,
                        )
                        st.success("BCBS 239 output created.")
                        rerun()

    with tabs[5]:
        st.info("The app no longer auto-seeds EUC operational data on startup. Use the button below only when you explicitly want to load demo EUCs.")
        if st.button("Run seed data loader", type="secondary"):
            seed_database(force=False)
            st.success("Seed loader executed. Existing records were not overwritten.")

        st.divider()
        st.subheader("Delete all EUC operational data")
        st.error(
            "This deletes EUCs and related operational records: assets, risk assessments, uploaded evidence records, "
            "tasks, reviews, findings, exceptions, incidents, material changes, and queued notifications. "
            "User profiles, RACI rules, reference data, required artifact rules, due-date rules, and the audit trail are preserved."
        )
        confirm = st.text_input("Type DELETE EUC DATA to enable the purge button", key="purge_euc_data_confirm")
        if st.button("Delete all EUC operational data", type="primary", disabled=confirm != "DELETE EUC DATA"):
            result = svc.delete_all_euc_operational_data(username)
            st.success("EUC operational data deleted. Users, configuration, and audit trail were preserved.")
            st.write(result)
            rerun()



def page_notifications() -> None:
    st.title("Email Notifications")
    username, role = current_user()
    if role not in NOTIFICATION_ACCESS_ROLES:
        st.warning("Email Notifications are restricted to GCC, Data Validation Unit, and Group IT Governance Administrator users.")
        return
    st.caption("Email actions are queued from the RACI matrix. SMTP sending is optional and controlled by environment variables.")

    tabs = st.tabs(["Notification outbox", "RACI email rules", "SMTP configuration"])
    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        statuses = ["All"] + svc.notification_statuses()
        events = ["All"] + svc.notification_event_types()
        status_filter = c1.selectbox("Status", statuses)
        event_filter = c2.selectbox("Event type", events)
        recipient_filter = c3.text_input("Recipient contains")
        outbox = svc.notification_outbox_table({"status": status_filter, "event_type": event_filter, "recipient": recipient_filter})
        display_cols = [
            "notification_id", "status", "event_type", "activity_decision", "reference_id", "recipient_username",
            "recipient_email", "recipient_role", "raci_party", "raci_responsibility", "created_at", "sent_at", "error_message",
        ]
        safe_df(outbox[[c for c in display_cols if c in outbox.columns]] if not outbox.empty else outbox, height=460)
        csv_download(outbox, "notification_outbox.csv")

        st.markdown("#### Send / manage selected notifications")
        c4, c5 = st.columns(2)
        limit = c4.number_input("Maximum pending emails to send", min_value=1, max_value=500, value=25, step=5)
        if c5.button("Send pending via SMTP", type="primary"):
            try:
                result = svc.send_pending_notifications(int(limit), username)
                st.success(f"Attempted {result['attempted']} notification(s). Sent: {result['sent']}; failed: {result['failed']}.")
                rerun()
            except Exception as exc:
                st.error(str(exc))

        if not outbox.empty:
            labels = {
                f"{row['notification_id']} — {row['event_type']} — {row.get('recipient_email') or row.get('recipient_username') or 'no recipient'}": int(row["notification_id"])
                for _, row in outbox.iterrows()
            }
            chosen = st.selectbox("Select notification to update manually", list(labels.keys()))
            c6, c7 = st.columns(2)
            manual_status = c6.selectbox("Manual status", ["Pending", "Sent", "Failed", "Cancelled", "No Email"])
            manual_error = c7.text_input("Status note / error message")
            if st.button("Update notification status"):
                svc.update_notification_status(labels[chosen], manual_status, username, manual_error or None)
                st.success("Notification status updated.")
                rerun()

    with tabs[1]:
        st.markdown("#### RACI-driven email rules")
        rules = svc.raci_rules_table(active_only=False)
        safe_df(rules, height=420)
        csv_download(rules, "raci_email_rules.csv")
        if role == svc.ADMIN_ROLE and not rules.empty:
            st.markdown("#### Edit selected RACI rule")
            labels = {f"{row['event_type']} — {row['activity_decision']}": int(row["rule_id"]) for _, row in rules.iterrows()}
            chosen_rule = st.selectbox("Rule", list(labels.keys()))
            rule = rules[rules["rule_id"] == labels[chosen_rule]].iloc[0].to_dict()
            with st.form("edit_raci_rule"):
                activity = st.text_input("Activity / decision", value=rule.get("activity_decision") or "")
                c1, c2, c3, c4 = st.columns(4)
                raci_options = ["-", "A", "R", "A/R", "C", "I", "A/R (checks)", "R (submit)", "C (provide info)", "R (findings)", "A (raise)"]
                euc_owner = c1.selectbox("EUC Owner", raci_options, index=option_index(raci_options, rule.get("euc_owner_raci")))
                dvu = c2.selectbox("Data Validation Unit", raci_options, index=option_index(raci_options, rule.get("data_validation_unit_raci")))
                gcc = c3.selectbox("GCC", raci_options, index=option_index(raci_options, rule.get("gcc_raci")))
                group_it = c4.selectbox("Group IT Governance", raci_options, index=option_index(raci_options, rule.get("group_it_governance_raci")))
                c5, c6, c7, c8 = st.columns(4)
                iof = c5.selectbox("IOF", raci_options, index=option_index(raci_options, rule.get("iof_raci")))
                data_gov = c6.selectbox("Data Governance", raci_options, index=option_index(raci_options, rule.get("data_governance_raci")))
                audit = c7.selectbox("Internal Audit", raci_options, index=option_index(raci_options, rule.get("internal_audit_raci")))
                grm = c8.selectbox("GRM Strategy / Projects", raci_options, index=option_index(raci_options, rule.get("grm_strategy_raci")))
                active = st.checkbox("Active", value=bool(rule.get("active_flag")))
                comments = st.text_area("Maker-checker comments", value=rule.get("maker_checker_comments") or "")
                if st.form_submit_button("Save RACI rule"):
                    svc.update_raci_rule(
                        int(rule["rule_id"]),
                        {
                            "activity_decision": activity,
                            "euc_owner_raci": euc_owner,
                            "data_validation_unit_raci": dvu,
                            "gcc_raci": gcc,
                            "group_it_governance_raci": group_it,
                            "iof_raci": iof,
                            "data_governance_raci": data_gov,
                            "internal_audit_raci": audit,
                            "grm_strategy_raci": grm,
                            "active_flag": active,
                            "maker_checker_comments": comments,
                        },
                        username,
                    )
                    st.success("RACI email rule updated.")
                    rerun()
        elif role != svc.ADMIN_ROLE:
            st.info("Only Group IT Governance Administrator can edit RACI rules. GCC and Data Validation can view and export them.")

    with tabs[2]:
        st.markdown("#### Optional SMTP environment variables")
        st.write("The MVP queues email actions even when no SMTP server is configured. To send emails, configure these environment variables in Streamlit Cloud or the local shell:")
        st.code("""SMTP_HOST=smtp.example.internal
SMTP_PORT=587
SMTP_FROM=ekassotis@eurobank.gr
SMTP_USER=<optional>
SMTP_PASSWORD=<optional>
SMTP_USE_TLS=true""", language="bash")
        st.info("If SMTP_HOST is missing, the Send button leaves notifications in Pending status and shows a configuration warning. SMTP_FROM defaults to ekassotis@eurobank.gr, while recipient addresses come from the editable User Directory.")

def page_audit() -> None:
    st.title("Audit Trail")
    username, role = current_user()
    if role not in AUDIT_ACCESS_ROLES:
        st.warning("Audit Trail is restricted to GCC users.")
        return
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
    _, role = current_user()
    if not can_access_page(page, role):
        st.warning("You do not have access to this page with the current role.")
        return
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
        "Email Notifications": page_notifications,
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
