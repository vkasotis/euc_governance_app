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

RACI_NOTIFICATION_ROLES = [
    "IOF",
    "Data Governance",
    "GRM Strategy & Oversight / Projects (Group Finance)",
]

DIRECTORY_ROLES = ROLES + RACI_NOTIFICATION_ROLES

RACI_PARTIES = [
    "EUC Owner",
    "Data Validation Unit",
    "GCC",
    "Group IT Governance",
    "IOF",
    "Data Governance",
    "Internal Audit",
    "GRM Strategy & Oversight / Projects (Group Finance)",
]

RACI_RULE_DEFINITIONS = [
    {
        "activity_decision": "Define EUC Policy & updates",
        "event_types": ["POLICY_UPDATED"],
        "raci": {"EUC Owner": "C", "Data Validation Unit": "C", "GCC": "A/R", "Group IT Governance": "C", "IOF": "C", "Data Governance": "C", "Internal Audit": "C", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Maintain EUC Register (platform, taxonomy, controls lists)",
        "event_types": ["REFERENCE_DATA_UPDATED", "ARTIFACT_RULE_UPDATED", "DUE_DATE_RULE_UPDATED", "USER_PROFILE_UPDATED"],
        "raci": {"EUC Owner": "C", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "A/R", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Maintain EUC Register entry (per EUC record accuracy & updates)",
        "event_types": ["EUC_REGISTERED", "EUC_UPDATED", "EUC_COMPONENT_UPDATED"],
        "raci": {"EUC Owner": "A/R", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "C", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Risk Assessment",
        "event_types": ["RISK_ASSESSMENT_COMPLETED"],
        "raci": {"EUC Owner": "A/R", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "C", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Implement controls",
        "event_types": ["EVIDENCE_SUBMITTED", "EVIDENCE_REVIEWED"],
        "raci": {"EUC Owner": "A", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "-", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Independent review",
        "event_types": ["INDEPENDENT_REVIEW_COMPLETED"],
        "raci": {"EUC Owner": "C", "Data Validation Unit": "A/R (checks)", "GCC": "C", "Group IT Governance": "-", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Material changes",
        "event_types": ["MATERIAL_CHANGE_LOGGED"],
        "raci": {"EUC Owner": "A", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "-", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Industrialization request (submit candidate)",
        "event_types": ["INDUSTRIALIZATION_REQUESTED"],
        "raci": {"EUC Owner": "R (submit)", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "C", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "C"},
    },
    {
        "activity_decision": "Industrialization assessment & prioritization decision",
        "event_types": ["INDUSTRIALIZATION_DECISION"],
        "raci": {"EUC Owner": "C (provide info)", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "-", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "A"},
    },
    {
        "activity_decision": "Incident handling",
        "event_types": ["INCIDENT_HANDLING_UPDATED"],
        "raci": {"EUC Owner": "A/R", "Data Validation Unit": "C", "GCC": "C", "Group IT Governance": "C", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Incident logging / maintenance of EUC Incident Log",
        "event_types": ["INCIDENT_LOGGED"],
        "raci": {"EUC Owner": "R", "Data Validation Unit": "C", "GCC": "A/R", "Group IT Governance": "I", "IOF": "I", "Data Governance": "I", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "Exceptions / risk acceptance",
        "event_types": ["EXCEPTION_RAISED", "EXCEPTION_DECISION"],
        "raci": {"EUC Owner": "A (raise)", "Data Validation Unit": "C", "GCC": "R", "Group IT Governance": "C", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
    {
        "activity_decision": "MI & governance reporting",
        "event_types": ["FINDING_RAISED", "GOVERNANCE_REPORT_REFRESHED"],
        "raci": {"EUC Owner": "C", "Data Validation Unit": "R (findings)", "GCC": "A/R", "Group IT Governance": "C", "IOF": "C", "Data Governance": "C", "Internal Audit": "I", "GRM Strategy & Oversight / Projects (Group Finance)": "-"},
    },
]

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
        materiality_q1 TEXT,
        materiality_q2 TEXT,
        materiality_q3 TEXT,
        materially_supports_bcbs239 TEXT,
        owner_integrity_inherent TEXT,
        owner_timeliness_inherent TEXT,
        effective_integrity_inherent TEXT,
        effective_timeliness_inherent TEXT,
        integrity_control_effectiveness TEXT,
        timeliness_control_effectiveness TEXT,
        integrity_residual_risk TEXT,
        timeliness_residual_risk TEXT,
        overall_inherent_risk TEXT,
        overall_residual_risk TEXT,
        required_action TEXT,
        control_registration_risk_assessment TEXT,
        control_privileged_access TEXT,
        control_versioning_change_log TEXT,
        control_checks_reconciliations TEXT,
        control_library_controls_cacrt TEXT,
        control_operating_procedure TEXT,
        control_evidence_signoff TEXT,
        control_resilience TEXT,
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
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT,
        email TEXT,
        role TEXT NOT NULL,
        active_flag INTEGER NOT NULL DEFAULT 1,
        maker_checker_comments TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL,
        updated_by TEXT,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS raci_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_decision TEXT NOT NULL,
        event_type TEXT NOT NULL UNIQUE,
        euc_owner_raci TEXT,
        data_validation_unit_raci TEXT,
        gcc_raci TEXT,
        group_it_governance_raci TEXT,
        iof_raci TEXT,
        data_governance_raci TEXT,
        internal_audit_raci TEXT,
        grm_strategy_raci TEXT,
        active_flag INTEGER NOT NULL DEFAULT 1,
        maker_checker_comments TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_outbox (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        activity_decision TEXT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        euc_id INTEGER,
        reference_id TEXT,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        recipient_username TEXT,
        recipient_email TEXT,
        recipient_role TEXT,
        raci_party TEXT,
        raci_responsibility TEXT,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        sent_at TEXT,
        error_message TEXT,
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
    "CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(role, active_flag);",
    "CREATE INDEX IF NOT EXISTS idx_raci_rules_event ON raci_rules(event_type, active_flag);",
    "CREATE INDEX IF NOT EXISTS idx_notification_outbox_status ON notification_outbox(status, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_notification_outbox_event ON notification_outbox(event_type, entity_type, entity_id);",
]
