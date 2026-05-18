"""Database schema and reference configuration for the EUC Governance MVP."""

from __future__ import annotations

APP_TITLE = "End-to-End EUC Governance Monitoring App"
BANK_NAME = "Eurobank S.A."
DB_PATH = "euc_governance.db"
UPLOAD_DIR = "uploads"

ROLES = [
    "EUC Owner",
    "EUC Owner Delegate / Contributor",
    "GCC",
    "Data Validation Unit",
    "Group IT Governance Administrator",
    "Approver / Head of Unit",
    "Internal Audit / Read-only User",
]

ROLE_SHORT_NAMES = {
    "EUC Owner": "Owner",
    "EUC Owner Delegate / Contributor": "Contributor",
    "GCC": "GCC",
    "Data Validation Unit": "DVU",
    "Group IT Governance Administrator": "Admin",
    "Approver / Head of Unit": "Approver",
    "Internal Audit / Read-only User": "Audit",
}

LIFECYCLE_STATUSES = [
    "Draft",
    "Submitted",
    "Registered",
    "Risk Assessment In Progress",
    "Awaiting Documentation",
    "Review Ready",
    "Active",
    "Under Remediation",
    "Exception Active",
    "Incident Open",
    "Under Change",
    "Awaiting Reassessment",
    "Industrialization Candidate",
    "Decommissioned",
    "Archived",
]

OVERALL_STATUSES = [
    "Draft",
    "Submitted",
    "Registered",
    "Review-ready",
    "Active",
    "Under remediation",
    "Under change",
    "Exception active",
    "Incident open",
    "Industrialization candidate",
    "Decommissioned",
    "Archived",
]

RISK_LEVELS = ["Low", "Medium", "High", "Very High"]

TECHNOLOGY_TYPES = [
    "MS Excel",
    "MS Access",
    "VBA",
    "Python",
    "Python script",
    "Notebook",
    "SQL Script",
    "SQL script",
    "SAS",
    "Power BI",
    "Databricks - Workbook",
    "Database Tables",
    "Report",
    "Manual process",
    "Document",
    "MS Word",
    "MS Power Point",
    "CSV File (CSV)",
    "Text File (TXT)",
    "EVIEW Files",
    "Refinitiv EIKON platform",
    "Other",
]

LEGAL_ENTITIES = [
    "Eurobank S.A.",
    "Eurobank Leasing",
    "Eurobank Factoring",
    "Eurobank Bulgaria",
    "Eurobank Luxembourg",
    "Eurobank Cyprus",
]

YES_NO = ["Yes", "No"]
CONTROL_STORAGE_TYPES = ["Document Server", "SharePoint Server", "Database Server", "Databricks", "Other"]
DATA_CLASSIFICATIONS = ["Public", "Internal", "Confidential", "Restricted", "Highly Restricted"]
INPUT_SOURCE_TYPES = ["CDW", "Databricks", "Altamira", "AS400", "File", "API", "Manual input", "Other"]
AUTOMATION_LEVELS = ["Manual", "Partially Automated", "Fully Automated"]
RISK_ASSESSMENT_TYPES = ["Periodic", "Material Change", "Incident-triggered", "Manual trigger"]
CONTROL_STATUSES = ["In place and evidenced", "Partially in place", "Not in place", "N/A"]
CONTROL_EFFECTIVENESS_LEVELS = ["Strong", "Adequate", "Weak", "Not in place"]
RISK_DIMENSIONS = ["Integrity / Accuracy", "Timeliness / Availability"]
BASELINE_CONTROL_AREAS = [
    "1. Registration & risk assessment",
    "2. Privileged Access",
    "3. Versioning & change log",
    "4. Checks & reconciliations",
    "5. EUC Library of Controls (CACRT)",
    "6. Operating Procedure",
    "7. Evidence & sign-off",
    "8. Resilience",
]

BCBS_MATERIALITY_QUESTIONS = [
    "Failure or error could render the relevant BCBS 239 in-scope output materially inaccurate, incomplete, delayed or unavailable",
    "EUC constitutes a key control point within the process, where its outcome can directly trigger correction, rejection, restatement, escalation, or delayed issuance of a BCBS 239 in-scope output",
    "EUC represents a single point of failure within a critical reporting or risk process supporting a BCBS 239 in-scope output",
]


FREQUENCIES = ["Daily", "Weekly", "Monthly", "Quarterly", "Biannually", "Annually", "Ad hoc", "Event-driven"]

DOCUMENT_TYPES = [
    "Risk Assessment",
    "Operating Procedure",
    "Library of Controls",
    "Testing Evidence",
    "UAT Evidence",
    "Approval Evidence",
    "Review Evidence",
    "Reconciliation Evidence",
    "Resilience Evidence",
    "Exception Record",
    "Incident Evidence",
    "Decommissioning Evidence",
]

DOCUMENT_STATUSES = [
    "Pending",
    "Submitted",
    "Accepted",
    "Rejected",
    "Expired",
    "Superseded",
    "Missing",
]

CONTROL_AREAS = [
    "Ownership & Accountability",
    "Inventory & Classification",
    "Data Inputs & Lineage",
    "Data Validation",
    "Change Management",
    "Access Control",
    "Operational Resilience",
    "Reconciliation & Controls",
    "Issue Management",
    "Decommissioning",
]

CACRT_DIMENSIONS = [
    "Completeness",
    "Accuracy",
    "Consistency",
    "Reasonableness",
    "Timeliness",
    "Traceability",
]

TASK_TYPES = [
    "Registration completion",
    "Risk assessment",
    "Document submission",
    "Missing evidence",
    "Remediation",
    "Reassessment",
    "Review response",
    "Closure evidence",
    "Documentation refresh",
]

TASK_STATUSES = ["Open", "In Progress", "Blocked", "Closure Requested", "Closed", "Cancelled"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
FINDING_SEVERITIES = ["Low", "Medium", "High", "Critical"]
REVIEW_OUTCOMES = ["Accepted", "Accepted with comments", "Returned for remediation", "Finding raised"]
REVIEW_TYPES = ["Data Validation", "GCC Monitoring", "Closure Validation", "Periodic Review"]
APPROVAL_STATUSES = ["Pending", "Approved", "Rejected", "Expired", "Withdrawn"]
INCIDENT_STATUSES = ["Open", "Contained", "RCA In Progress", "Remediation In Progress", "Closed"]
CHANGE_TYPES = ["Logic", "Inputs", "Outputs", "Recipients", "Thresholds", "Security", "Storage", "Dependencies", "Platform", "Other"]
REFERENCE_CATEGORIES = [
    "document_type",
    "lifecycle_status",
    "risk_level",
    "control_area",
    "cacrt_dimension",
    "due_date_rule",
]

DEFAULT_REQUIRED_ARTIFACTS = {
    "Low": ["Risk Assessment", "Operating Procedure"],
    "Medium": ["Risk Assessment", "Operating Procedure", "Library of Controls", "Review Evidence"],
    "High": [
        "Risk Assessment",
        "Operating Procedure",
        "Library of Controls",
        "Testing Evidence",
        "Reconciliation Evidence",
        "Review Evidence",
    ],
    "Very High": [
        "Risk Assessment",
        "Operating Procedure",
        "Library of Controls",
        "Testing Evidence",
        "Reconciliation Evidence",
        "Resilience Evidence",
        "Review Evidence",
        "Approval Evidence",
    ],
}

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS eucs (
        euc_id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        purpose TEXT,
        legal_entity TEXT DEFAULT 'Eurobank S.A.',
        owner TEXT NOT NULL,
        owner_delegate TEXT,
        reviewer TEXT,
        business_unit TEXT NOT NULL,
        technology_type TEXT NOT NULL,
        storage_location TEXT NOT NULL,
        frequency TEXT,
        schedule TEXT,
        cut_off TEXT,
        business_context TEXT,
        bcbs239_output_mapping TEXT NOT NULL,
        cde_linkage TEXT,
        inputs TEXT,
        outputs TEXT,
        recipients TEXT,
        dependencies TEXT,
        spof_indicator TEXT DEFAULT 'No',
        supports_material_report TEXT DEFAULT 'No',
        supports_material_kri TEXT DEFAULT 'No',
        supports_material_model TEXT DEFAULT 'No',
        used_by_multiple_bus TEXT DEFAULT 'No',
        number_active_users TEXT,
        created_by_bu TEXT DEFAULT 'Yes',
        acquired_third_party TEXT DEFAULT 'No',
        support_contract_sla TEXT DEFAULT 'No',
        library_of_controls TEXT,
        last_risk_assessment TEXT,
        exceptions_remediation_actions TEXT,
        industrialization_decommissioning_status TEXT,
        materially_supports_bcbs239 TEXT DEFAULT 'No',
        materiality_rationale TEXT,
        inherent_risk TEXT DEFAULT 'Medium',
        residual_risk TEXT DEFAULT 'Medium',
        overall_status TEXT DEFAULT 'Draft',
        documentation_completeness_status TEXT DEFAULT 'Not Checked',
        lifecycle_status TEXT DEFAULT 'Draft',
        next_review_date TEXT,
        industrialization_rationale TEXT,
        decommissioning_rationale TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        mapping_na_justification TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS components (
        component_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        component_name TEXT NOT NULL,
        component_type TEXT NOT NULL,
        technology TEXT,
        business_unit TEXT,
        euc_application TEXT,
        material_report_mapping TEXT,
        operationalization_document_link TEXT,
        storage_location TEXT,
        controlled_storage_type TEXT,
        input_sources TEXT,
        cut_off_times TEXT,
        processing_schedule TEXT,
        execution_frequency TEXT,
        cde_mappings TEXT,
        data_outputs TEXT,
        level_of_automation TEXT,
        backup_recovery_arrangements TEXT,
        spof_risk TEXT,
        modification_date TEXT,
        review_date TEXT,
        description TEXT,
        criticality TEXT,
        owner TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_assessments (
        assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        assessment_date TEXT NOT NULL,
        assessed_by TEXT NOT NULL,
        assessment_type TEXT,
        materiality_q1 TEXT,
        materiality_q2 TEXT,
        materiality_q3 TEXT,
        materially_supports_bcbs239 TEXT,
        owner_integrity_level TEXT,
        owner_timeliness_level TEXT,
        effective_integrity_level TEXT,
        effective_timeliness_level TEXT,
        integrity_control_effectiveness TEXT,
        timeliness_control_effectiveness TEXT,
        integrity_residual_level TEXT,
        timeliness_residual_level TEXT,
        integrity_rationale TEXT,
        timeliness_rationale TEXT,
        control_assessment_json TEXT,
        required_action_guidance TEXT,
        integrity_accuracy_score INTEGER NOT NULL,
        timeliness_availability_score INTEGER NOT NULL,
        complexity_score INTEGER NOT NULL,
        business_criticality_score INTEGER NOT NULL,
        control_effectiveness_score INTEGER NOT NULL,
        inherent_risk TEXT NOT NULL,
        residual_risk TEXT NOT NULL,
        rationale TEXT,
        trigger_type TEXT,
        version INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        document_type TEXT NOT NULL,
        requirement TEXT,
        control_area TEXT,
        cacrt_dimension TEXT,
        risk_applicability TEXT,
        lifecycle_stage TEXT,
        version TEXT,
        status TEXT NOT NULL,
        uploaded_by TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        reviewed_by TEXT,
        reviewed_at TEXT,
        comments TEXT,
        deficiency_tag TEXT,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS required_artifact_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        risk_level TEXT NOT NULL,
        lifecycle_stage TEXT NOT NULL,
        required_document_type TEXT NOT NULL,
        control_area TEXT,
        cacrt_dimension TEXT,
        mandatory_flag INTEGER NOT NULL DEFAULT 1,
        maker_checker_comments TEXT,
        proposed_by TEXT,
        approved_by TEXT,
        approval_status TEXT DEFAULT 'Approved'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER,
        task_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        assigned_to TEXT,
        assigned_role TEXT,
        due_date TEXT,
        status TEXT NOT NULL,
        priority TEXT,
        closure_reason TEXT,
        closure_evidence_document_id INTEGER,
        created_at TEXT NOT NULL,
        closed_at TEXT,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id),
        FOREIGN KEY (closure_evidence_document_id) REFERENCES documents(document_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS findings (
        finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        review_id INTEGER,
        severity TEXT NOT NULL,
        requirement TEXT,
        control_area TEXT,
        finding_description TEXT NOT NULL,
        remediation_required TEXT,
        assigned_to TEXT,
        due_date TEXT,
        status TEXT NOT NULL,
        closure_comments TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        closed_at TEXT,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id),
        FOREIGN KEY (review_id) REFERENCES reviews(review_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS reviews (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        reviewer TEXT NOT NULL,
        reviewer_role TEXT NOT NULL,
        review_type TEXT NOT NULL,
        outcome TEXT NOT NULL,
        comments TEXT,
        review_date TEXT NOT NULL,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS exceptions (
        exception_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        control_gap TEXT NOT NULL,
        root_cause TEXT,
        compensating_controls TEXT,
        residual_risk TEXT,
        remediation_plan TEXT,
        target_date TEXT,
        expiry_date TEXT,
        approval_status TEXT,
        approved_by TEXT,
        status TEXT,
        created_at TEXT NOT NULL,
        closure_evidence_document_id INTEGER,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id),
        FOREIGN KEY (closure_evidence_document_id) REFERENCES documents(document_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        affected_outputs TEXT,
        incident_date TEXT NOT NULL,
        impact_summary TEXT,
        containment_status TEXT,
        correction_status TEXT,
        rca_status TEXT,
        remediation_actions TEXT,
        status TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS material_changes (
        change_id INTEGER PRIMARY KEY AUTOINCREMENT,
        euc_id INTEGER NOT NULL,
        change_type TEXT NOT NULL,
        description TEXT NOT NULL,
        impact_assessment TEXT,
        reassessment_required INTEGER NOT NULL DEFAULT 0,
        documentation_refresh_required INTEGER NOT NULL DEFAULT 0,
        status TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (euc_id) REFERENCES eucs(euc_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_trail (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        performed_by TEXT NOT NULL,
        performed_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS reference_data (
        ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        value TEXT NOT NULL,
        active_flag INTEGER NOT NULL DEFAULT 1,
        maker_checker_comments TEXT,
        proposed_by TEXT,
        approved_by TEXT,
        approval_status TEXT DEFAULT 'Approved',
        UNIQUE(category, value)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS due_date_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        risk_level TEXT,
        due_days INTEGER NOT NULL,
        active_flag INTEGER NOT NULL DEFAULT 1,
        maker_checker_comments TEXT,
        proposed_by TEXT,
        approved_by TEXT,
        approval_status TEXT DEFAULT 'Approved',
        UNIQUE(task_type, risk_level)
    );
    """,
]

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_eucs_owner ON eucs(owner);",
    "CREATE INDEX IF NOT EXISTS idx_eucs_status ON eucs(lifecycle_status);",
    "CREATE INDEX IF NOT EXISTS idx_docs_euc_type ON documents(euc_id, document_type);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_role_status ON tasks(assigned_role, status);",
    "CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);",
    "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_trail(entity_type, entity_id);",
]
