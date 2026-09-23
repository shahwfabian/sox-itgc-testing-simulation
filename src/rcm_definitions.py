"""Risk and Control Matrix content (Phase 1).

Originally structured for this simulation. Terminology follows COSO 2013 and
PCAOB AS 2201 conventions, but this is not any real company's RCM.
"""

# Inherent risk rating: likelihood (1-5) x impact (1-5) = severity score (1-25).
RISKS = [
    {
        "risk_id": "R-01",
        "title": "Unauthorized access to financial applications",
        "statement": (
            "Users are granted access to in-scope financial applications without "
            "documented business-owner approval, or retain access that is no longer "
            "commensurate with their role, allowing unauthorized or erroneous "
            "transactions to be recorded in the general ledger and subledgers."
        ),
        "assertions": "Occurrence; Accuracy; Existence",
        "fs_impact": "Unauthorized journal entries, loan adjustments or payments recorded in financial statements",
        "likelihood": 3, "impact": 4,
    },
    {
        "risk_id": "R-02",
        "title": "Terminated users retain system access",
        "statement": (
            "Access for terminated employees and contractors is not removed timely, "
            "allowing former personnel (or others using their credentials) to "
            "initiate or approve transactions after separation."
        ),
        "assertions": "Occurrence; Existence",
        "fs_impact": "Fraudulent or unauthorized transactions posted under a departed user's ID",
        "likelihood": 3, "impact": 5,
    },
    {
        "risk_id": "R-03",
        "title": "Inappropriate privileged access",
        "statement": (
            "Privileged (administrator, superuser, DBA) access is granted without "
            "independent authorization, enabling users to bypass application "
            "controls, alter configurations, or modify financial data directly."
        ),
        "assertions": "Occurrence; Accuracy; Completeness",
        "fs_impact": "Direct data changes or disabled automated controls that bypass segregation of duties",
        "likelihood": 3, "impact": 5,
    },
    {
        "risk_id": "R-04",
        "title": "Unauthorized changes to financial systems",
        "statement": (
            "Changes to applications, interfaces, or configurations supporting "
            "financial reporting are implemented to production without independent "
            "approval, introducing processing or calculation errors."
        ),
        "assertions": "Accuracy; Completeness; Valuation",
        "fs_impact": "Misstated balances from faulty calculations, interfaces or report logic",
        "likelihood": 3, "impact": 4,
    },
    {
        "risk_id": "R-05",
        "title": "Failed changes cannot be reversed",
        "statement": (
            "Production changes are implemented without a documented back-out "
            "(rollback) plan, so a failed change causes prolonged processing "
            "outages or corrupted financial data that cannot be restored reliably."
        ),
        "assertions": "Completeness; Accuracy",
        "fs_impact": "Incomplete or corrupted period-end data; delayed close",
        "likelihood": 2, "impact": 3,
    },
]


def severity(risk):
    score = risk["likelihood"] * risk["impact"]
    rating = "Critical" if score >= 15 else "High" if score >= 10 else "Medium" if score >= 5 else "Low"
    return score, rating


CONTROLS = [
    # ---------------- User access: provisioning / deprovisioning ----------------
    {
        "control_id": "ITGC-UA-01", "risk_id": "R-01", "domain": "User Access",
        "title": "New user access approval",
        "description": (
            "Requests for new or modified (non-privileged) access to in-scope financial "
            "applications are submitted through the access request system and approved "
            "by the user's manager before the IT Access Management team provisions access. "
            "Provisioning without a recorded approver is not permitted."
        ),
        "owner": "IT Access Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "IT-dependent manual", "key": "Yes",
        "population": "data/user_access_log.csv (non-privileged grants dated within FY2025)",
        "attribute": "Grant has a recorded approver who is not the grantee.",
        "procedure": (
            "Obtain the FY2025 access provisioning log; filter to non-privileged grants in "
            "period; confirm each grant carries an approver ID and that the approver is "
            "not the grantee."
        ),
    },
    {
        "control_id": "ITGC-UA-02", "risk_id": "R-02", "domain": "User Access",
        "title": "Timely revocation of terminated users",
        "description": (
            "Upon notification of a separation, IT Access Management removes all "
            "application access for the terminated user within five (5) business days "
            "of the termination date."
        ),
        "owner": "IT Access Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "IT-dependent manual", "key": "Yes",
        "population": "data/termination_log.csv joined to data/user_access_log.csv",
        "attribute": "Every grant held at the termination date ends within 5 business days after it.",
        "procedure": (
            "Obtain the HR termination listing for FY2025 and the access log; for each "
            "terminated employee identify all grants active at the termination date; "
            "compute business days from termination to access end date; flag grants "
            "revoked after the SLA or still active at the as-of date."
        ),
    },
    {
        "control_id": "ITGC-UA-03", "risk_id": "R-02", "domain": "User Access",
        "title": "HR separation notification",
        "description": (
            "HR Operations notifies IT Access Management of each separation via the HR "
            "system feed or ticket within one (1) business day of the termination date, "
            "triggering the revocation workflow."
        ),
        "owner": "HR Operations Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "IT-dependent manual", "key": "No",
        "population": "data/termination_log.csv (terminations dated within FY2025)",
        "attribute": "HR-notified date is no more than 1 business day after termination date.",
        "procedure": (
            "For each FY2025 termination compute business days between the termination "
            "date and the HR-notified date; flag notifications later than 1 business day."
        ),
    },
    {
        "control_id": "ITGC-UA-04", "risk_id": "R-01", "domain": "User Access",
        "title": "Quarterly user access review",
        "description": (
            "Each quarter, application owners review a system-generated listing of all "
            "user and privileged accounts for each in-scope application, certify "
            "appropriateness and request removal of inappropriate access. Reviews are "
            "completed within 30 days of quarter end."
        ),
        "owner": "Application Owner", "frequency": "Quarterly",
        "type": "Detective", "nature": "Manual", "key": "Yes",
        "population": "data/access_reviews.csv (4 systems x 4 quarters)",
        "attribute": "Review completed, by an assigned reviewer, on or before the due date.",
        "procedure": (
            "Obtain the FY2025 access review tracker; confirm a review exists for every "
            "system-quarter, that it was completed on or before the due date and that "
            "a reviewer is recorded."
        ),
    },
    # ---------------- Privileged access management ----------------
    {
        "control_id": "ITGC-PA-01", "risk_id": "R-03", "domain": "Privileged Access",
        "title": "Privileged access authorization",
        "description": (
            "Privileged access (Administrator, Superuser, Database Administrator) is "
            "granted only upon a documented approval from the system owner in the "
            "privileged access approval register, matching the requested system and "
            "access level, and dated on or before the grant."
        ),
        "owner": "Information Security Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "IT-dependent manual", "key": "Yes",
        "population": "data/user_access_log.csv (privileged grants in FY2025) vs data/privileged_access_approvals.csv",
        "attribute": "Matching approval record (ticket, employee, system, access level) dated on/before the grant date.",
        "procedure": (
            "Filter the access log to privileged access levels granted in FY2025; match "
            "each grant to the approval register by request ticket; confirm employee, "
            "system and access level agree and approval date <= grant date."
        ),
    },
    {
        "control_id": "ITGC-PA-02", "risk_id": "R-03", "domain": "Privileged Access",
        "title": "Independent approval of privileged access",
        "description": (
            "Approvers of privileged access requests must be independent of the "
            "requester; self-approval is prohibited and blocked by workflow configuration."
        ),
        "owner": "Information Security Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "Automated", "key": "Yes",
        "population": "data/privileged_access_approvals.csv (approvals for FY2025 privileged grants)",
        "attribute": "Approver ID differs from the employee receiving access.",
        "procedure": (
            "For each privileged approval record supporting an FY2025 grant, compare the "
            "approver ID to the grantee ID; flag self-approvals."
        ),
    },
    # ---------------- Change management ----------------
    {
        "control_id": "ITGC-CM-01", "risk_id": "R-04", "domain": "Change Management",
        "title": "Change approval prior to implementation",
        "description": (
            "Normal and standard changes to in-scope applications are approved by the "
            "Change Advisory Board (CAB) prior to production implementation. Emergency "
            "changes may be implemented first but must be retrospectively approved "
            "within two (2) business days."
        ),
        "owner": "Change Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "IT-dependent manual", "key": "Yes",
        "population": "data/change_log.csv (changes implemented in FY2025)",
        "attribute": "Approver recorded; approval before implementation (emergency: within 2 BD after).",
        "procedure": (
            "Obtain the FY2025 production change log; for each change confirm an approver "
            "and approval timestamp exist; for normal/standard changes confirm approval "
            "precedes implementation; for emergency changes confirm approval within 2 "
            "business days after implementation."
        ),
    },
    {
        "control_id": "ITGC-CM-02", "risk_id": "R-05", "domain": "Change Management",
        "title": "Documented rollback plan",
        "description": (
            "Every production change record includes a documented back-out (rollback) "
            "plan, reviewed by the CAB as part of change approval."
        ),
        "owner": "Change Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "Manual", "key": "No",
        "population": "data/change_log.csv (changes implemented in FY2025)",
        "attribute": "Rollback plan field indicates a documented plan exists.",
        "procedure": (
            "Normalize the rollback-plan indicator (Yes/Y/yes/No/N) and flag changes "
            "without a documented rollback plan."
        ),
    },
    {
        "control_id": "ITGC-CM-03", "risk_id": "R-04", "domain": "Change Management",
        "title": "Segregation of duties in change approval",
        "description": (
            "The individual approving a change cannot be the individual who requested "
            "or developed it."
        ),
        "owner": "Change Manager", "frequency": "As needed (per event)",
        "type": "Preventive", "nature": "IT-dependent manual", "key": "Yes",
        "population": "data/change_log.csv (approved changes implemented in FY2025)",
        "attribute": "Approver ID differs from requester ID.",
        "procedure": "Compare requested_by to approved_by for each approved change; flag matches.",
    },
]

DOMAINS = ["User Access", "Privileged Access", "Change Management"]


def risk_by_id(rid):
    return next(r for r in RISKS if r["risk_id"] == rid)


def control_by_id(cid):
    return next(c for c in CONTROLS if c["control_id"] == cid)
