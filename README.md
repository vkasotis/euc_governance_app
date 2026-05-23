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

## Dashboard visibility note

The Home / Dashboard page uses a personal scope. It shows EUCs, tasks, findings, exceptions, incidents, and charts relevant to the logged-in user context: owned EUCs, delegated EUCs, records created by the user, tasks assigned to the user, and role-queue tasks for centralized governance roles. Portfolio-wide monitoring remains available through the GCC Monitoring View and Reports & KPIs pages according to role permissions.

## Patch note: Admin User Directory

The Group IT Governance Administrator can manage users from `Admin Configuration` -> `User directory`.

1. Log in with role `Group IT Governance Administrator`.
2. Open `Admin Configuration` from the sidebar.
3. Open the `User directory` tab.
4. Select a user row in the table, or use the fallback `Selected user` dropdown.
5. Update username, full name, email, role, active flag, and comments.
6. Click `Save selected user`.

User profile changes are written to the audit trail. Active users also feed the MVP login username suggestions for each role.

## Patch note: regression cleanup

This version removes raw JSON-style review panels from the business UI. Completed risk assessments, EUC summary fields, and mapping fields are now rendered as normal field/value tables and workbook-style review sections. Duplicate detection during registration has also been tightened to avoid flagging unrelated EUCs only because they share the same business unit or owner.

### Patch note - task visibility

The **Tasks & Remediation** page is user-scoped. When a role and username are selected at login, the page shows only tasks directly assigned to that username, tasks assigned to that role queue, and, for EUC Owner / Contributor users, tasks linked to EUCs they own, are delegated to, or created. Portfolio-wide task reporting remains available in GCC Monitoring and Reports.

### Patch note - reports and audit navigation

The sidebar now hides restricted pages based on the selected role:

- `Reports & KPIs` is available only to `GCC`, `Data Validation Unit`, and `Group IT Governance Administrator`.
- `Audit Trail` is available only to `GCC`.

The page functions also enforce the same restrictions if a restricted route is reached directly.

### Patch note - RACI-based email actions

The app now includes a local notification outbox driven by the Appendix 6 RACI matrix.

New capabilities:

- `Email Notifications` page for `GCC`, `Data Validation Unit`, and `Group IT Governance Administrator`.
- `notification_outbox` table for queued email actions.
- `raci_rules` table for event-to-RACI routing.
- User Directory support for notification-only groups: `IOF`, `Data Governance`, and `GRM Strategy & Oversight / Projects (Group Finance)`.
- Automatic notification queuing for key governance actions:
  - EUC registration and EUC updates
  - EUC component updates
  - risk assessment completion
  - evidence submission and review
  - independent review completion
  - findings raised
  - exceptions raised and exception decisions
  - incidents logged
  - material changes logged
  - industrialization requests
  - task assignment and task updates
  - reference data / required artifact rule / user directory changes

The MVP queues notifications even when no mail server is configured. To enable actual SMTP sending, set these environment variables before running Streamlit:

```bash
SMTP_HOST=smtp.example.internal
SMTP_PORT=587
SMTP_FROM=ekassotis@eurobank.gr
SMTP_USER=<optional>
SMTP_PASSWORD=<optional>
SMTP_USE_TLS=true
```

When SMTP_HOST is not configured, notifications remain in `Pending` status and can be exported or manually statused from the `Email Notifications` page.

## Automated task closure

The MVP now auto-closes workflow tasks when the underlying user action is completed:

- Submitting a risk assessment closes open Risk assessment / Reassessment tasks for the EUC.
- Completing the Risk Assessment module also satisfies and closes missing Risk Assessment evidence tasks.
- Uploading evidence closes the relevant Document submission / Missing evidence / Closure evidence task where the task text matches the uploaded document type.
- Accepting evidence repeats the closure check in case the workflow expects reviewer acceptance.
- Approving or rejecting an exception closes the related exception-approval task.
- Closing a finding closes the matching remediation task.

All automated closures write an audit-trail entry with action `AUTO_CLOSE` and queue a task-update notification where the notification outbox is enabled.

## Patch note - editable notification emails

Seeded demo users are initialized with `ekassotis@eurobank.gr` so a fresh demo routes all notifications to the same mailbox by default. This is no longer hard-forced at runtime. Group IT Governance Administrators can edit user email addresses from `Admin Configuration` -> `User directory`, and new notification outbox records use the recipient email currently stored in the User Directory.

## Patch 18 updates

### Opening uploaded evidence

Uploaded evidence is now shown with one-click **Open** links wherever uploaded documentation is displayed, including the EUC Detail View and Documents & Evidence Pack. Streamlit does not expose local files as static web assets, so the MVP generates browser-openable data links for the locally stored file. PDF, image, and text evidence generally opens in a new browser tab; Office files may download depending on browser support.

### Deleting EUC operational data

Group IT Governance Administrator users can use **Admin Configuration → Seed/reset demo → Delete all EUC operational data** to clear EUC-specific operational records while preserving users and configuration. The purge removes EUCs, assets, risk assessments, uploaded evidence records, tasks, reviews, findings, exceptions, incidents, material changes, queued notifications, and local upload files. User profiles, RACI rules, reference data, required artifact rules, due-date rules, and the audit trail are preserved. The purge action itself is recorded in the audit trail.

After a purge, automatic demo reseeding is disabled until the seed loader is run manually from the same Admin page or by running `python seed_data.py`.

## Document access note

Uploaded evidence is stored locally under `uploads/`. The UI uses Streamlit download buttons for Office and other binary evidence so that the browser receives the original bytes with an appropriate file name/extension. Browser previews are shown only for previewable formats such as PDF, images, text, CSV, JSON, and XML.

## Patch 20 - automatic documentation lifecycle synchronization

When the Required Artifact Checklist is recalculated or when relevant actions occur, the app now synchronizes the EUC master record automatically:

- all mandatory artifacts accepted or internally satisfied -> `documentation_completeness_status = Complete` and eligible pre-review EUCs move to `Review Ready`;
- missing, rejected, or expired mandatory artifacts -> `documentation_completeness_status = Incomplete` and eligible pre-review EUCs remain or move to `Awaiting Documentation`;
- submitted but not yet accepted mandatory artifacts -> `documentation_completeness_status = Submitted - Pending Review` and eligible pre-review EUCs remain or move to `Awaiting Documentation`.

The synchronization avoids overriding protected governance statuses such as `Active`, `Under Remediation`, `Exception Active`, `Incident Open`, `Under Change`, `Industrialization Candidate`, `Decommissioned`, and `Archived`.

## Patch 21 - policy-correct artifact baseline

The Required Artifact Checklist now follows the policy/control matrix interpretation:

- required evidence baseline is driven by **Overall Inherent Risk**;
- BCBS 239 materiality applies the **Very High** inherent-risk baseline, even where residual risk is reduced to Medium by strong controls;
- residual risk no longer reduces the evidence baseline;
- residual risk now drives remediation, escalation and exception-related workflow tasks;
- event-driven overlays add targeted requirements for SPOF, incidents, material changes, exceptions, industrialization candidates and decommissioning.

The Admin Configuration required-artifact rule label was updated to clarify that risk level refers to the **Overall inherent risk baseline**. Existing administrator rules are still used, but the policy default baseline is always included so older local databases do not retain a residual-risk-only checklist.

## Patch 23 regression merge notes

This version restores the fuller application feature set from the previous stable build and merges the policy/checklist refinements from v22.

Restored capabilities include the User Directory, RACI notification outbox, role-sensitive navigation, scoped dashboards and task queues, Components / Assets row selection and edit, Excel-aligned risk assessment, business-friendly assessment review display, document open/download controls, simplified evidence upload, risk assessments shown as internal evidence, lifecycle/completeness synchronization, automatic task closure, page-level edit forms, and governed record deletion for GCC/Admin where supported.

Merged v22 refinements include:

- Required artifacts are driven by Overall Inherent Risk / BCBS materiality baseline.
- The checklist includes `what_to_upload` guidance for every artifact type.
- Owner-completed risk assessments are stored as `Submitted` and must be reviewed to become `Accepted`.
- The app no longer auto-seeds EUC operational data on startup. Demo EUCs are loaded only via Admin Configuration -> Seed/reset demo or by running `python seed_data.py`.

