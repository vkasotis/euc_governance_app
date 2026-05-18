# End-to-End EUC Governance Monitoring App

Production-style MVP Streamlit application for Eurobank S.A. to demonstrate end-to-end EUC governance monitoring, risk assessment, evidence tracking, Data Validation review, GCC oversight, findings, exceptions, incidents, material changes, lifecycle management, reporting, role-based UI access, and audit trail.

## Scope

This MVP is intentionally self-contained:

- Python and Streamlit web UI
- SQLite database stored locally as `euc_governance.db`
- Local evidence/document storage under `uploads/`
- No external APIs
- No enterprise SSO; authentication is represented by a simple Streamlit session-state role and username selector
- Modular code structure to allow later replacement of authentication, database, and workflow services

## Project structure

```text
.
├── app.py                  # Streamlit UI and page routing
├── db.py                   # SQLite connection, query helpers, audit helper
├── schema.py               # Schema DDL and reference constants
├── services.py             # Governance logic, workflows, scoring, checklist, RBAC helpers
├── seed_data.py            # Representative demo portfolio and seed data loader
├── requirements.txt        # Python dependencies
├── README.md               # Local and deployment instructions
├── .streamlit/config.toml  # Streamlit theme and server settings
└── uploads/                # Local evidence/document storage
```


## Uploaded workbook alignment

The current version was adjusted after reviewing the two uploaded workbooks:

- `1. EUC Inventory.xlsm`
  - `EUC Inventory` sheet: master EUC register fields.
  - `EUC Asset Inventory` sheet: one-to-many asset/component rows belonging to a parent EUC.
  - `LOV` sheet: reference values for legal entities, business units, technology types, storage types, input sources, SPOF, frequency, and automation level.
- `2. EUC Risk_Assessement.xlsx`
  - `Assessment` sheet: risk assessment form and formulas.
  - `Lookups` sheet: risk levels, control statuses, assessment types, residual matrix, and EUC lookup data.
  - `Dimensions & Risk Levels` sheet: definitions and guidance.

The app does not require these Excel files at runtime; their rules and fields are represented in the SQLite schema, Streamlit forms, and `services.py` governance logic.

## Features

### Governance modules

The app contains the following navigation areas:

1. Home / Dashboard
2. EUC Inventory
3. Register New EUC
4. EUC Detail View
5. Components / Assets
6. Risk Assessment
7. Documents & Evidence Pack
8. Required Artifact Checklist
9. Tasks & Remediation
10. Data Validation Review Queue
11. GCC Monitoring View
12. Findings & Challenge Management
13. Exceptions
14. Incidents & Near Misses
15. Material Changes & Reassessments
16. Industrialization & Decommissioning
17. Reports & KPIs
18. Admin Configuration
19. Audit Trail

### User roles

The MVP supports role-based UI restrictions for:

- EUC Owner
- EUC Owner Delegate / Contributor
- GCC
- Data Validation Unit
- Group IT Governance Administrator
- Approver / Head of Unit
- Internal Audit / Read-only User

The login is a demo scaffold only. It is isolated in the Streamlit session-state layer so it can be replaced by SSO or a reverse-proxy identity provider later.

### Governance logic implemented

- Unique EUC reference generation using the workbook-style `EUC.001` convention
- Duplicate hints using name, owner, business unit, and storage location
- BCBS 239 output mapping requirement
- `Not Applicable` mapping justification check
- Multiple EUC Asset Inventory rows for one logical EUC, linked through `euc_id`
- Registration fields aligned to the uploaded EUC Inventory workbook, including Legal Entity, Reviewer, material report/KRI/model flags, active users, BU/COTS/SLA indicators, Library of Controls, and industrialization/decommissioning status
- Risk assessment methodology aligned to the uploaded workbook: BCBS 239 materiality questions, Integrity / Accuracy and Timeliness / Availability dimensions, baseline control assessment, derived control effectiveness, residual-risk matrix, required action guidance, and full assessment history
- Automatic inherent/residual risk update on assessment submission
- Evidence upload to local `/uploads` storage
- Evidence metadata: document type, requirement, control area, CACRT dimension, lifecycle stage, risk applicability, version, and status
- GCC/Data Validation evidence review with accept/reject/comment/deficiency tagging
- Required artifact checklist based on residual risk
- Automatic follow-up tasks for missing/rejected/expired mandatory artifacts
- Data Validation review queue and independent reviewer check
- Findings with automatic remediation task creation
- Exception workflow with Approver / Head of Unit approval
- Incident creation with reassessment and documentation refresh task generation
- Material change capture with reassessment and documentation refresh triggers
- Industrialization candidate and controlled decommissioning flow
- Dashboard cards, charts, reporting filters, and CSV export
- Immutable audit trail viewer from the UI
- Admin reference data and required artifact rule management, including maker-checker comment fields

## Risk assessment methodology

The Risk Assessment page implements the logic from the uploaded `EUC Risk_Assessement.xlsx` workbook rather than the original five-slider MVP rule.

The assessment flow is:

1. Capture assessment metadata and assessment type: Periodic, Material Change, Incident-triggered, or Manual trigger.
2. Capture three BCBS 239 materiality questions. If any answer is `Yes`, the EUC is treated as materially supporting a BCBS 239 in-scope output.
3. Capture owner inherent levels for the two policy dimensions:
   - Integrity / Accuracy
   - Timeliness / Availability
4. If the EUC materially supports BCBS 239, the effective inherent risk for both dimensions is forced to `Very High`.
5. Capture the eight baseline control areas:
   - Registration & risk assessment
   - Privileged Access
   - Versioning & change log
   - Checks & reconciliations
   - EUC Library of Controls (CACRT)
   - Operating Procedure
   - Evidence & sign-off
   - Resilience
6. Derive control effectiveness as `Strong`, `Adequate`, `Weak`, or `Not in place` using the workbook rule.
7. Apply the residual-risk matrix from the workbook to determine residual risk by dimension and overall residual risk. Material BCBS-supporting EUCs cannot fall below Medium residual risk.

The older average-score helper remains only as a backwards-compatible fallback for legacy seed or migration payloads.

## Required artifact logic

Default mandatory evidence rules:

| Residual risk | Required artifacts |
|---|---|
| Low | Risk Assessment, Operating Procedure |
| Medium | Risk Assessment, Operating Procedure, Library of Controls, Review Evidence |
| High | Risk Assessment, Operating Procedure, Library of Controls, Testing Evidence, Reconciliation Evidence, Review Evidence |
| Very High | Risk Assessment, Operating Procedure, Library of Controls, Testing Evidence, Reconciliation Evidence, Resilience Evidence, Review Evidence, Approval Evidence |

These rules are inserted into the `required_artifact_rules` table and can be extended from Admin Configuration.

## Local run

Use Python 3.10+.

```bash
cd euc_governance_app
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

On first run, the app initializes the SQLite schema, reference data, a demo portfolio, and local upload folders automatically if no EUC records exist.

You can also seed manually:

```bash
python seed_data.py
```

## Demo users

Use the sidebar to select a role and username. Suggested demo usernames are pre-populated by role:

| Role | Example username |
|---|---|
| EUC Owner | Maria.Papadopoulou |
| EUC Owner Delegate / Contributor | EUC.Contributor |
| GCC | GCC.User |
| Data Validation Unit | DVU.Reviewer |
| Group IT Governance Administrator | Admin.User |
| Approver / Head of Unit | Head.Of.Unit |
| Internal Audit / Read-only User | Internal.Audit |

## Streamlit Community Cloud deployment

1. Push this project folder to a Git repository.
2. Ensure `requirements.txt` is in the repository root or configure Streamlit to use the app subfolder.
3. In Streamlit Community Cloud, create a new app and set the entry point to:

```text
app.py
```

4. The app will create `euc_governance.db` and `uploads/` in the app runtime storage. Note that Community Cloud ephemeral storage may reset across redeployments or container restarts.

## Production hardening considerations

For a production implementation, replace or extend the MVP with:

- Enterprise SSO and group/entitlement mapping
- Central database such as PostgreSQL or SQL Server
- Object storage for evidence files
- Encryption at rest and virus scanning for uploads
- Fine-grained row-level authorization
- Maker-checker approval for reference data and workflow configuration
- Scheduled jobs for ageing, expiry, overdue checks, and notifications
- Versioned evidence retention and legal hold policies
- Data lineage integration and integration with issue-management tooling
- Deployment to a controlled Eurobank environment with audit and monitoring controls

## Reset local demo data

To fully reset the local MVP during development:

```bash
rm -f euc_governance.db
rm -rf uploads/euc_*
streamlit run app.py
```

The app will recreate seed data on next launch.
