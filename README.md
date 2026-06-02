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
