# End-to-End EUC Governance Monitoring App

Production-style MVP Streamlit app for Eurobank S.A. EUC governance monitoring aligned to the updated EUC Policy and appendices.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Current policy-aligned behavior

- Minimum controls and evidence baselines are driven primarily by **Overall Inherent Risk**.
- Residual Risk does **not** reduce the baseline; it drives remediation, escalation and exception handling.
- EUCs materially supporting BCBS 239 in-scope outputs apply the enhanced Very High baseline for Integrity/Accuracy and Timeliness/Availability.
- Legacy onboarding uses a **current-state evidence baseline** and does not require retrospective recreation of historical Testing, UAT, Approval or historical change evidence where unavailable.
- The app does not impose fixed annual / semi-annual / quarterly access-review frequencies. Access evidence is risk/event-driven and focuses on named roles, ACL/RLS where applicable, privileged access control, and leaver/role-change revocation.
- Design / Logic Evidence is conditional: it is required only where the EUC contains material business logic, automated processing, complex calculations, scripts, macros, transformations, critical assumptions or mappings that cannot be adequately understood through the Operating Procedure alone.
- Evidence Pack Index is not a required upload. The app itself acts as the evidence index through the Documents & Evidence Pack, checklist, statuses and audit trail.

## Required documentation baseline

| Overall Inherent Risk | Standing baseline documentation |
|---|---|
| Low | Risk Assessment; Operating Procedure / run notes |
| Medium | Risk Assessment; Operating Procedure; Change & Versioning Evidence; Control Evidence; Review Evidence |
| High | Risk Assessment; Operating Procedure; Library of Controls; Change & Versioning Evidence; Reconciliation Evidence; Review Evidence; Access Review Evidence; Resilience Evidence |
| Very High | Risk Assessment; Operating Procedure; Library of Controls; Change & Versioning Evidence; Reconciliation Evidence; Resilience Evidence; Review Evidence; Approval Evidence; Access Review Evidence |

## Conditional / event-driven evidence

| Trigger | Additional evidence |
|---|---|
| Design/logic applicability = Yes | Design / Logic Evidence |
| New EUC go-live | Testing Evidence; UAT Evidence; Approval Evidence |
| Legacy onboarding | Current-state control evidence, recent/current reconciliation where applicable, current review or management attestation; historical Testing/UAT/Approval/change evidence is not recreated solely for initial registration |
| Material change | Change & Versioning Evidence; Risk Assessment update; for High/Very High also Testing, UAT and Approval Evidence as applicable |
| Incident / near miss | Incident & RCA Evidence; Risk Assessment review/update; OP / Library updates where applicable |
| Exception | Exception Record; Approval Evidence where residual risk is High/Very High |
| SPOF = Yes | Resilience Evidence |
| Decommissioning | Decommissioning Evidence; Archive Evidence; Access Revocation Evidence |

## Key features preserved

- Option B role-based workbench and grouped menu
- Role-based page guards
- SQLite MVP database
- Local upload storage under `/uploads`
- EUC Application and EUC Asset Inventory parent-child model
- Risk assessment workflow with submitted/accepted/rejected statuses
- AgGrid tables with in-table filters and no rerun while typing
- Multi-file and multi-document-type evidence uploads
- Upload reset after save
- RACI notification outbox
- User directory and admin reference data
- Reports & KPIs
- No automatic operational EUC demo reseeding on startup

## Deployment notes

Commit and deploy the whole package together:

- `app.py`
- `services.py`
- `schema.py`
- `db.py`
- `seed_data.py`
- `requirements.txt`
- `README.md`
- `.streamlit/config.toml`

Do not commit local runtime data:

```gitignore
euc_governance.db
euc_governance.db-*
uploads/
__pycache__/
*.pyc
```

## Policy-completeness update excluding structured Library of Controls

This release implements the remaining policy-completeness items while keeping Library of Controls as an uploaded evidence attachment rather than a structured app module.

Implemented additions:
- Expanded EUC Application Inventory fields for registration/go-live dates, evidence-pack/library links, high-criticality flags, documentation-gap summary, materiality/mapping confidence and migration notes.
- Expanded EUC Asset Inventory fields for COTS/vendor support, approved environment, BYOD, input availability, run duration, timeliness monitoring, fallback/BCP, restore testing, deputy cover, key-person dependency, version/release, change log, release notes, retention/evidence location, data classification, external sharing, mapping confidence and migration/legacy flags.
- Fuller Appendix 7-style Incident Log capture, including detection date, reporting run, incident type, severity, CACRT dimension, root-cause category/description, containment, corrective/preventive actions, owner, resolution targets, regulatory impact, escalation, re-issue/restatement and evidence links.
- Risk-based material-change workflow fields covering change rationale, cut-over, rollback, DEV/UAT/PROD stage, testing/UAT/approval requirements, Library of Controls attachment refresh, Evidence Pack update, communications, emergency change and retro-UAT.
- Enhanced exception governance fields for milestones, monitoring approach, periodic review, renewal, escalation, Unit Head / Senior Management / BCBS 239 Steering indicators.
- Documentation Gap Assessment workflow for legacy onboarding and review gaps, with remediation task creation.
- High-Criticality Evidence Pack / Independent Review checklist for GCC/Data Validation review.
- Industrialization scoring and decision record based on policy criteria.
- Reports & KPIs additions for documentation gaps, high-criticality review coverage, and lineage completeness.

Library of Controls remains a document/evidence attachment type and is not implemented as a separate structured control-register module.

## Post-registration governance field placement

The Register New EUC page no longer asks EUC Owners for the former "Inventory completeness, evidence and migration summary" fields during initial registration. Those items are maintained after registration in the appropriate workflow locations:

- EUC Detail View: derived inventory completeness/governance status, registration/go-live dates, material mapping confidence and legacy flags.
- Documents & Evidence Pack: Evidence Pack index/location, Library of Controls attachment reference and optional external risk-assessment reference.
- Required Artifact Checklist: documentation gap assessment required flag, documentation gap summary and detailed documentation-gap workflow.
- GCC Monitoring View and Admin Configuration: portfolio-level inventory completeness/migration monitoring and migration metadata updates.

Library of Controls remains an uploaded attachment/evidence type rather than a structured database module.
