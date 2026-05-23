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

- Unique EUC reference generation such as `EUC-000001`
- Duplicate hints using name, owner, business unit, and storage location
- BCBS 239 output mapping requirement
- `Not Applicable` mapping justification check
- Multiple components/assets for one logical EUC
- Risk assessment scoring and full history
- Automatic risk and residual risk update on assessment submission
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

## Risk scoring rule

The MVP applies the configurable scoring convention implemented in `services.py`:

- Average score 1.0-1.9 = Low
- Average score 2.0-2.9 = Medium
- Average score 3.0-3.9 = High
- Average score 4.0-5.0 = Very High

Inherent risk is calculated from integrity/accuracy, timeliness/availability, complexity, and business criticality. Residual risk includes the control effectiveness score as the fifth score.

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

## Patch 22 notes

### Artifact evidence guidance

The Required Artifact Checklist now includes a `what_to_upload` column. This describes the evidence expected for each artifact type, for example access-review listings, approval emails, reconciliation packs, restore-drill evidence, UAT packs, or an evidence index.

### Risk assessment status

A risk assessment completed by an EUC Owner is now stored as `Submitted`. It is not treated as `Accepted` until GCC, Data Validation, or the Administrator reviews and accepts it in the Risk Assessment page. The checklist uses the assessment status directly.

### Demo data seeding

The application no longer automatically reseeds demo EUC data when the database has zero EUCs. Demo data can be loaded explicitly from Admin Configuration or by running `python seed_data.py`. This prevents operational data that was deleted from reappearing after a code redeploy.

### Operational data purge

Group IT Governance Administrator users can delete EUC operational data from Admin Configuration. This preserves configuration/reference data and audit trail.
