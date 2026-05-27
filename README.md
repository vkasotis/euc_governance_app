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
- Excel-aligned risk assessment with BCBS 239 materiality override, dimension-level inherent/residual risk, baseline controls, review status, and governed amendment workflow
- Automatic risk and residual risk update on assessment submission and reviewer acceptance
- Evidence upload to local `/uploads` storage with multi-file and multi-artifact-type support
- Simplified evidence upload with reviewer-driven status; required artifact guidance explains what to upload
- GCC/Data Validation evidence review with accept/reject/comment/deficiency tagging
- Required artifact checklist based on Overall Inherent Risk / BCBS 239 materiality baseline, with residual risk used for remediation/escalation
- Automatic follow-up tasks for missing/rejected/expired mandatory artifacts
- Data Validation review queue and independent reviewer check
- Findings with automatic remediation task creation
- Exception workflow with Approver / Head of Unit approval
- Incident creation with reassessment and documentation refresh task generation
- Material change capture with reassessment and documentation refresh triggers
- Industrialization candidate and controlled decommissioning flow
- Dashboard cards, charts, policy-ready MI/KPI report pack, custom report builder, and CSV export
- Immutable audit trail viewer from the UI
- Admin reference data and required artifact rule management, including maker-checker comment fields

## Risk assessment model

The MVP uses the Excel-aligned EUC Risk Assessment model implemented in `services.py`:

- BCBS 239 materiality questions determine whether the elevated-inherent-risk treatment applies.
- The EUC Owner selects owner inherent risk for Integrity / Accuracy and Timeliness / Availability from Low, Medium, or High.
- If any BCBS 239 materiality question is Yes, effective inherent risk for both dimensions is Very High.
- Eight baseline controls are assessed, with guidance shown in the UI.
- Control effectiveness is derived separately by dimension.
- Residual risk is calculated through the policy matrix and cannot fall below Medium for BCBS-material EUCs.
- New risk assessments are Submitted until accepted/rejected by GCC or Data Validation. Amendments require an approved edit request.

## Required artifact logic

Default mandatory evidence rules are driven by Overall Inherent Risk / BCBS 239 materiality baseline, not by residual risk. Residual risk drives remediation, escalation, and exception governance.

| Overall inherent-risk baseline | Required artifacts |
|---|---|
| Low | Risk Assessment, Operating Procedure |
| Medium | Risk Assessment, Operating Procedure, Change & Versioning Evidence, Control Evidence, Review Evidence |
| High | Risk Assessment, Operating Procedure, Library of Controls, Change & Versioning Evidence, Testing Evidence, Reconciliation Evidence, Review Evidence, Access Review Evidence, Resilience Evidence |
| Very High | Risk Assessment, Operating Procedure, Library of Controls, Change & Versioning Evidence, Design / Logic Evidence, Testing Evidence, UAT Evidence, Reconciliation Evidence, Resilience Evidence, Review Evidence, Approval Evidence, Access Review Evidence, Evidence Pack (dynamic in-app index) |

Additional event-driven overlays are added for SPOF, incidents, material changes, exceptions, industrialization, and decommissioning. These rules are inserted into the `required_artifact_rules` table and can be extended from Admin Configuration.

## Local run

Use Python 3.10+.

```bash
cd euc_governance_app
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

On first run, the app initializes the SQLite schema, reference/configuration data, and local upload folders. It does not automatically seed EUC operational/demo data.

You can seed demo EUC data manually from Admin Configuration -> Seed/reset demo, or from the command line:

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

The app will recreate schema/reference data on next launch. Demo EUC data is not recreated automatically; load it explicitly from Admin Configuration or `python seed_data.py`.

## Patch 28 updates

- Restored the fuller codebase and kept the previously implemented functionality: user directory, RACI notifications, personal scoping, Excel-aligned risk assessment, inherent-risk-driven artifact checklist, document open/download controls, task auto-closure, lifecycle/completeness synchronization, and admin operational-data purge.
- Evidence upload now supports multiple files and multiple artifact types in one submission. One file can cover several artifact types, and several files can be uploaded for the same artifact type.
- Risk assessments can now be amended in place only through a governed workflow: the EUC Owner/Delegate requests an amendment, GCC or Data Validation approves/rejects the request, and an approved amendment resets the assessment to Submitted for renewed review.
- Group IT Governance Administrator is treated as a platform/configuration administrator: it can maintain configuration and perform administrative reset activities, but it cannot register/edit EUC registry content or create/review/amend risk assessments.
- The Evidence & sign-off baseline control is preserved exactly as selected by the user. Only the Registration & Risk Assessment control is subject to the special system cap pending accepted risk assessment and registration/mapping completeness.

## Patch 30 updates

- Reports & KPIs now includes a policy-ready MI/KPI pack aligned to the EUC Policy, including inventory coverage and risk profile, EUC-to-BCBS 239 output coverage, inventory completeness/quality, Library of Controls KPIs, CACRT coverage, incident resolution, exception ageing, remediation/findings pipeline, industrialization/decommissioning pipeline, and overdue reviews.
- Added KPI cards for total EUCs, BCBS mapping, documentation completeness, High/Very High inherent/residual risk, overdue reviews, incidents, exceptions, remediation, industrialization, Library of Controls coverage, and operationalization documentation coverage.
- Added a Custom Reports tab allowing authorized reporting users to create reusable reports from approved datasets without SQL.
- Added the `custom_report_definitions` table and lightweight migration support for older SQLite databases.

## Patch 31 updates

- Documents & Evidence Pack now clears selected artifact types, uploaded files, and comments immediately after a successful evidence submission by rotating the Streamlit widget keys after save.
- Material Changes & Reassessments are treated as EUC Owner / operating-unit initiated records. Governance roles may review, challenge, monitor, or request remediation, but Group IT Governance remains platform/configuration administrator rather than owner of EUC content.
- Exceptions are treated as EUC Owner raised requests for temporary risk acceptance. GCC owns governance handling and tracking, Data Validation / relevant functions may be consulted, and approval is performed by the relevant Approver / Head of Unit or senior governance route depending on risk.

## Patch 32 updates

- Replaced the long sidebar radio navigation with a compact role-based workbench plus grouped sidebar navigation.
- The Home page now displays role-specific action cards. Each card routes the user to the relevant operational, review, governance, or administration page.
- Sidebar menu buttons are shown only for roles that should access those pages. Direct page access is also guarded by the same role/page matrix.
- Group IT Governance Administrator navigation is limited to platform/configuration, email-notification administration, and reports; it does not expose EUC registry, risk-assessment, evidence-upload, exception, incident, or material-change content workflows.
- EUC Owner, Contributor, Data Validation, GCC, Approver, and Internal Audit / read-only users each receive a different workbench and navigation scope aligned with their responsibilities.

## Patch 33 notes

- The Option B role-based Workbench menu remains the stable navigation pattern.
- Documents & Evidence Pack upload reset has been hardened: after saving evidence, the selected artifact types, uploaded files, and comments are cleared by rotating EUC-specific widget and form keys.
- The evidence upload flow explicitly confirms the number of evidence records to be created when one file is mapped to several document types or several files are uploaded for the same type.
- Uploaded file names now include microseconds and a short UUID segment to avoid overwriting files when multiple uploads have the same original filename.

## Patch 34 notes

- Documents & Evidence Pack now provides filters for every field in the Required Artifact Checklist.
- The checklist filter panel supports a global search across all fields, multi-select filters for low-cardinality columns, and contains-text filters for higher-cardinality columns.
- The same all-field checklist filtering is available on the standalone Required Artifact Checklist page.

## Table filtering and grid UX

All user-facing tabular views now use `streamlit-aggrid` where available. Each table supports in-grid column filters, floating filter boxes, sorting, resizing and filtered/sorted grid state. The app falls back to Streamlit's native dataframe rendering only if the optional component is not installed.

## Patch 37 notes

- AgGrid table readability has been improved across user-facing tables.
- Column headers now use readable labels instead of raw/truncated field names where possible.
- Column widths now use minimum readable widths and horizontal scrolling, rather than compressing all columns into the viewport.
- Long text cells wrap and show tooltips, so users can read full wording without relying on abbreviated column names.
- Existing in-table filters, no-rerun filtering behavior, Option B role-based menu, and evidence-upload reset behavior are preserved.

### Patch 38 notes
- Fixed assessment review detail sections that could render as blank AgGrid areas after the global table readability change.
- Operational/list/report tables continue to use AgGrid with in-table filters and no rerun while typing filters.
- Compact assessment detail sections now use native Streamlit tables for reliable display of baseline controls and required action/rationale.

## Latest registration field clarification

- **Frequency** captures how often the EUC is executed, for example Daily, Weekly, Monthly, Quarterly, Ad hoc, or Event-driven.
- **Execution schedule (working day)** is now a controlled dropdown from Working day 1 to Working day 90. It captures the business working day on which the EUC is normally executed, for example Working day 8.
- **Cut-off / delivery working day** is also a controlled dropdown from Working day 1 to Working day 90. It captures the latest business working day by which inputs, execution, or output delivery must be completed.
- **Description** explains what the EUC is.
- **Purpose** explains what the EUC is used for and what it produces or supports.
- **Business / reporting context** explains why the EUC matters in the wider business, reporting, control, or BCBS 239 process.

## Patch 41 notes

- Merged the confirmed EUC Inventory and EUC Asset Inventory workbook alignment into the latest app baseline.
- EUC Inventory now includes the additional parent/application fields from the workbook: legal entity, reviewer, material report/KRI/model mappings, multi-BU use, active user count, BU-created flag, third-party/COTS flag, support contract/SLA flag, and last risk assessment date.
- Legal Entity and Business Unit are controlled dropdowns maintained from Admin Configuration reference data.
- Owner, Owner Delegate and Reviewer are selected from the editable User Directory.
- Supports Material Report, Supports Material KRI and Supports Material Model are controlled dropdowns filtered from BCBS 239 outputs by output type: Material Report, Material KRI or Material Model.
- Last Risk Assessment date and overall inherent/residual risk are updated by the Risk Assessment module and are not manually maintained.
- Components / Assets has been expanded into the full EUC Asset Inventory child form linked to the parent EUC by `euc_id`. Parent Business Unit, Application and Reference ID are shown as read-only context.
- Asset fields now cover RRF Report/KRI/Model mapping, operationalization link, asset/file name, file description, technology, controlled storage type/location, inputs, cut-off, processing schedule, execution frequency, CDE mappings, outputs, automation level, backup/recovery, SPOF risk, modification date and review date.
- Existing confirmed behavior is preserved: Option B role-based menu, AgGrid no-rerun filters and readability, risk assessment workflow, evidence upload reset, multi-file/multi-type evidence upload, user directory, RACI notifications, reports, no automatic operational-data reseeding, and Group IT/admin content restrictions.

## Patch 43 notes

- Fixed an AgGrid startup/runtime error in EUC Detail View and other joined tables when a dataframe contains duplicate column names.
- The grid helper now deduplicates display column names before rendering and tolerates Pandas returning a DataFrame instead of a Series during column-width estimation.
- No business logic, permissions, risk assessment logic, evidence handling, RACI notifications, or inventory field mappings were changed in this patch.
