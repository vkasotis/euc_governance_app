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
    "Excel",
    "Access",
    "Python script",
    "Notebook",
    "Report",
    "SQL script",
    "Manual process",
    "Other",
]

FREQUENCIES = ["Daily", "Weekly", "Monthly", "Quarterly", "Ad hoc", "Event-driven"]

DOCUMENT_TYPES = [
    "Risk Assessment",
    "Operating Procedure",
    "Library of Controls",
    "Versioning / Change Log Evidence",
    "Design / Logic Evidence",
    "Control Evidence",
    "Testing Evidence",
    "UAT Evidence",
    "Approval Evidence",
    "Access Review Evidence",
    "Independent / Periodic Review Evidence",
    "Review Evidence",
    "Reconciliation Evidence",
    "Resilience Evidence",
    "Evidence Pack Index",
    "Exception Record",
    "Incident Evidence",
    "Incident RCA Evidence",
    "Containment / Correction Evidence",
    "Change Evidence",
    "Archive Evidence",
    "Access Revocation Evidence",
    "Industrialization Assessment Evidence",
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
    # Baseline artifact rules are driven by Overall Inherent Risk.
    # Residual risk drives remediation / escalation / exception workflow, not reduced documentation.
    "Low": ["Risk Assessment", "Operating Procedure"],
    "Medium": [
        "Risk Assessment",
        "Operating Procedure",
        "Versioning / Change Log Evidence",
        "Control Evidence",
        "Independent / Periodic Review Evidence",
    ],
    "High": [
        "Risk Assessment",
        "Operating Procedure",
        "Library of Controls",
        "Versioning / Change Log Evidence",
        "Testing Evidence",
        "Access Review Evidence",
        "Reconciliation Evidence",
        "Independent / Periodic Review Evidence",
    ],
    "Very High": [
        "Risk Assessment",
        "Operating Procedure",
        "Library of Controls",
        "Versioning / Change Log Evidence",
        "Design / Logic Evidence",
        "Control Evidence",
        "Testing Evidence",
        "UAT Evidence",
        "Access Review Evidence",
        "Reconciliation Evidence",
        "Resilience Evidence",
        "Approval Evidence",
        "Independent / Periodic Review Evidence",
        "Evidence Pack Index",
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
        owner TEXT NOT NULL,
        owner_delegate TEXT,
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
        storage_location TEXT,
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
        status TEXT NOT NULL DEFAULT 'Submitted',
        reviewed_by TEXT,
        reviewed_at TEXT,
        review_comments TEXT,
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
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT,
        updated_by TEXT,
        updated_at TEXT
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
