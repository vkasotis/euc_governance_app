"""Seed data for the EUC Governance MVP demo."""

from __future__ import annotations

from datetime import date, timedelta

from db import init_db, table_count
from services import (
    APPROVER_ROLE,
    DVU_ROLE,
    GCC_ROLE,
    OWNER_ROLE,
    create_component,
    create_document_record,
    create_euc,
    create_exception,
    create_finding,
    create_incident,
    create_material_change,
    create_risk_assessment,
    create_task,
    evaluate_and_update_completeness,
    initialize_reference_data,
    save_document_file,
    update_euc_status,
)

SEED_USER = "Admin.User"


def _doc(euc_id: int, doc_type: str, status: str, uploaded_by: str = SEED_USER, comments: str = "Seed evidence") -> int:
    file_name, file_path = save_document_file(
        euc_id,
        f"{doc_type.replace(' ', '_')}.txt",
        f"Demo evidence for {doc_type} linked to EUC {euc_id}.\n".encode("utf-8"),
    )
    return create_document_record(
        {
            "euc_id": euc_id,
            "file_name": file_name,
            "file_path": file_path,
            "document_type": doc_type,
            "requirement": f"Mandatory {doc_type}",
            "control_area": "Reconciliation & Controls" if "Reconciliation" in doc_type else "Ownership & Accountability",
            "cacrt_dimension": "Completeness",
            "risk_applicability": "All",
            "lifecycle_stage": "Active",
            "version": "1.0",
            "status": status,
            "comments": comments,
        },
        uploaded_by,
    )


def seed_database(force: bool = False) -> None:
    """Create a representative demo portfolio. Safe to run repeatedly unless force is True."""
    init_db()
    initialize_reference_data(SEED_USER)
    if table_count("eucs") > 0 and not force:
        return

    owners = ["Maria.Papadopoulou", "Nikos.Georgiou", "Elena.Dimitriou", "Kostas.Ioannou"]
    delegates = ["EUC.Contributor", "Christina.Markou", "EUC.Contributor", "Christina.Markou"]
    business_units = ["Risk Management", "Finance", "Treasury", "Retail Banking", "Corporate Banking"]
    euc_specs = [
        ("Credit RWA Monthly Reconciliation", "Excel", "Risk Management", "High", [4, 3, 4, 4, 3], "Yes"),
        ("Liquidity Coverage Ratio Support Tool", "Python script", "Treasury", "Very High", [5, 4, 4, 5, 4], "Yes"),
        ("IFRS9 Overlay Calculator", "Excel", "Finance", "High", [4, 4, 3, 4, 3], "No"),
        ("Retail Arrears Exception Tracker", "Access", "Retail Banking", "Medium", [3, 2, 3, 3, 2], "No"),
        ("Corporate Watchlist Manual Report", "Manual process", "Corporate Banking", "Medium", [2, 3, 2, 3, 2], "Yes"),
        ("Collateral Haircut Parameter Sheet", "Excel", "Risk Management", "Low", [1, 2, 1, 2, 1], "No"),
        ("Regulatory FINREP Bridge", "SQL script", "Finance", "Very High", [5, 4, 4, 5, 5], "No"),
        ("Stress Test Scenario Notebook", "Notebook", "Risk Management", "High", [4, 4, 4, 4, 3], "No"),
        ("Daily ALM Position Extract", "Report", "Treasury", "Medium", [3, 3, 2, 3, 2], "No"),
        ("Legacy MIS Decommission Candidate", "Access", "Retail Banking", "Low", [2, 1, 2, 1, 1], "No"),
    ]

    created_ids: list[int] = []
    for idx, (name, tech, unit, _risk, scores, spof) in enumerate(euc_specs):
        owner = owners[idx % len(owners)]
        delegate = delegates[idx % len(delegates)]
        euc_id = create_euc(
            {
                "name": name,
                "description": f"Seeded MVP EUC for {unit}.",
                "purpose": "Supports regulatory, management, or control reporting.",
                "legal_entity": "Eurobank S.A.",
                "owner": owner,
                "owner_delegate": delegate,
                "reviewer": "DVU.Reviewer",
                "business_unit": unit,
                "technology_type": tech,
                "storage_location": f"//eurobank/euc/{unit.lower().replace(' ', '_')}/{idx+1}",
                "frequency": "Monthly" if idx % 3 else "Daily",
                "schedule": "T+3 close process" if idx % 2 else "08:00 CET daily run",
                "cut_off": "18:00 CET",
                "business_context": "BCBS 239 management reporting and control evidence.",
                "supports_material_report": "Yes" if idx % 2 == 0 else "No",
                "supports_material_kri": "No",
                "supports_material_model": "No",
                "multi_bu_use": "Yes" if idx % 4 == 0 else "No",
                "active_user_count": 3 + idx,
                "created_by_bu": "Yes",
                "acquired_third_party_cots": "No",
                "support_contract_sla": "Not Applicable",
                "bcbs239_output_mapping": "Capital adequacy output" if idx % 2 else "Liquidity and risk data aggregation output",
                "inputs": "Data warehouse extracts; manual adjustments; golden source reports",
                "outputs": "Validated report pack; exception list; management sign-off summary",
                "recipients": "Business unit head; GCC; Data Validation Unit",
                "dependencies": "Data warehouse; network drive; upstream source owners",
                "spof_indicator": spof,
                "next_review_date": (date.today() + timedelta(days=45 - idx * 12)).isoformat(),
            },
            SEED_USER,
        )
        created_ids.append(euc_id)
        create_risk_assessment(
            {
                "euc_id": euc_id,
                "assessment_date": (date.today() - timedelta(days=idx * 7)).isoformat(),
                "assessed_by": owner,
                "integrity_accuracy_score": scores[0],
                "timeliness_availability_score": scores[1],
                "complexity_score": scores[2],
                "business_criticality_score": scores[3],
                "control_effectiveness_score": scores[4],
                "rationale": "Seeded assessment using MVP scoring rule.",
                "trigger_type": "Periodic review",
            },
            owner,
        )
        for n in range(2):
            create_component(
                {
                    "euc_id": euc_id,
                    "component_name": f"{name} component {n+1}",
                    "component_type": tech if n == 0 else ("SQL script" if tech != "SQL script" else "Operating Procedure"),
                    "technology": tech,
                    "storage_location": f"//eurobank/euc/components/{idx+1}/{n+1}",
                    "description": "Seeded component record.",
                    "cde_mappings": "Customer ID; Exposure Amount; Counterparty ID" if n == 0 else "Account Number; Currency; Outstanding Balance",
                    "data_outputs": "Validated report pack; exception list" if n == 0 else "Control totals; supporting extract",
                    "input_sources": "Data warehouse extracts; upstream source files",
                    "criticality": "High" if scores[0] >= 4 else "Medium",
                    "owner": owner,
                },
                SEED_USER,
            )

    # Evidence mix: accepted, submitted, rejected, and intentionally missing artifacts.
    for euc_id in created_ids[:7]:
        _doc(euc_id, "Risk Assessment", "Accepted")
        _doc(euc_id, "Operating Procedure", "Accepted")
    for euc_id in created_ids[1:5]:
        _doc(euc_id, "Library of Controls", "Submitted")
    _doc(created_ids[0], "Testing Evidence", "Rejected", comments="Sample size not sufficient for operating effectiveness conclusion.")
    _doc(created_ids[1], "Reconciliation Evidence", "Accepted")
    _doc(created_ids[1], "Resilience Evidence", "Submitted")
    _doc(created_ids[2], "Review Evidence", "Expired")
    _doc(created_ids[6], "Approval Evidence", "Accepted")
    _doc(created_ids[9], "Decommissioning Evidence", "Submitted")

    # Findings and overdue remediation.
    create_finding(
        {
            "euc_id": created_ids[0],
            "severity": "High",
            "requirement": "Testing Evidence",
            "control_area": "Reconciliation & Controls",
            "finding_description": "Testing pack does not evidence independent validation over key formulas.",
            "remediation_required": "Refresh testing evidence and add peer-review sign-off.",
            "assigned_to": "Maria.Papadopoulou",
            "due_date": (date.today() - timedelta(days=10)).isoformat(),
            "status": "Open",
        },
        "DVU.Reviewer",
    )
    create_finding(
        {
            "euc_id": created_ids[6],
            "severity": "Critical",
            "requirement": "Access Control",
            "control_area": "Access Control",
            "finding_description": "Privileged shared folder access identified for Very High EUC.",
            "remediation_required": "Remove generic access and implement named access review.",
            "assigned_to": "Elena.Dimitriou",
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
            "status": "Open",
        },
        "GCC.User",
    )
    create_task(
        created_ids[2],
        "Remediation",
        "Overdue remediation for expired review evidence",
        "Refresh expired review evidence and request closure validation.",
        "Elena.Dimitriou",
        OWNER_ROLE,
        (date.today() - timedelta(days=5)).isoformat(),
        "High",
        SEED_USER,
    )

    # Exceptions, incidents, and material changes.
    create_exception(
        {
            "euc_id": created_ids[3],
            "control_gap": "Automated reconciliation is not yet available for upstream exception feed.",
            "root_cause": "Legacy upstream format limitation.",
            "compensating_controls": "Manual four-eye review and sampled reconciliation.",
            "residual_risk": "Medium",
            "remediation_plan": "Implement automated reconciliation after source migration.",
            "target_date": (date.today() + timedelta(days=60)).isoformat(),
            "expiry_date": (date.today() + timedelta(days=90)).isoformat(),
            "approval_status": "Pending",
            "status": "Open",
        },
        "GCC.User",
    )
    create_incident(
        {
            "euc_id": created_ids[1],
            "affected_outputs": "Daily LCR pack",
            "incident_date": (date.today() - timedelta(days=2)).isoformat(),
            "impact_summary": "Delayed feed caused late delivery of liquidity support metrics.",
            "containment_status": "Contained",
            "correction_status": "Correction in progress",
            "rca_status": "RCA in progress",
            "remediation_actions": "Add pre-run data availability check and fallback extract.",
            "status": "Open",
        },
        "Nikos.Georgiou",
    )
    create_material_change(
        {
            "euc_id": created_ids[7],
            "change_type": "Inputs",
            "description": "New macroeconomic scenario feed added to stress test notebook.",
            "impact_assessment": "Potential impact on assumptions, controls, and UAT evidence.",
            "reassessment_required": True,
            "documentation_refresh_required": True,
            "status": "Open",
        },
        "Maria.Papadopoulou",
    )

    update_euc_status(created_ids[4], "Industrialization Candidate", SEED_USER, "Industrialization candidate")
    update_euc_status(created_ids[9], "Decommissioned", SEED_USER, "Decommissioned")

    # Set a review-ready example and refresh completeness flags.
    update_euc_status(created_ids[5], "Review Ready", SEED_USER, "Review-ready")
    for euc_id in created_ids:
        evaluate_and_update_completeness(euc_id, SEED_USER, create_missing_tasks=True)


if __name__ == "__main__":
    seed_database(force=False)
    print("Seed data ready.")
