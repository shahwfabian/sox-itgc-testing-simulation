"""Phase 3 - test every RCM control against the Phase 2 populations (pandas).

Reads ONLY data/*.csv and the policy parameters in common.py. It never opens
answer_key/ - exceptions are discovered from the data, then reconciled to the
answer key separately in validate_against_answer_key.py.

Outputs:
  outputs/exceptions/<CONTROL>_exceptions.csv   one traceable row per exception
  outputs/exceptions/all_exceptions.csv
  outputs/test_results_summary.csv              population / exceptions / conclusion
  outputs/ITGC_Testing_Results.xlsx             workbook of all of the above
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import common as C
from rcm_definitions import CONTROLS, control_by_id, risk_by_id, severity

POPULATIONS: dict[str, int] = {}


def load():
    d = C.DATA_DIR
    log = pd.read_csv(d / "user_access_log.csv", parse_dates=["date_granted", "access_end_date"])
    term = pd.read_csv(d / "termination_log.csv", parse_dates=["termination_date", "hr_notified_date"])
    appr = pd.read_csv(d / "privileged_access_approvals.csv", parse_dates=["approval_date"])
    rev = pd.read_csv(d / "access_reviews.csv", parse_dates=["quarter_end", "due_date", "completion_date"])
    chg = pd.read_csv(d / "change_log.csv", parse_dates=["approval_date", "implementation_date"])
    return log, term, appr, rev, chg


def in_period(s: pd.Series) -> pd.Series:
    return s.between(C.PERIOD_START, C.PERIOD_END + pd.Timedelta(hours=23, minutes=59))


def frame(control_id, df, **cols) -> pd.DataFrame:
    """Build the standard exception layout (every row traceable to a source record)."""
    out = pd.DataFrame({k: (df[v] if isinstance(v, str) and v in df else v) for k, v in cols.items()},
                       index=df.index)
    out.insert(0, "control_id", control_id)
    return out.reset_index(drop=True)


# --------------------------------------------------------------- user access
def test_ua01(log):
    pop = log[in_period(log.date_granted) & log.access_level.isin(C.STANDARD_ACCESS_LEVELS)]
    POPULATIONS["ITGC-UA-01"] = len(pop)
    exc = pop[pop.approver_id.isna() | (pop.approver_id == pop.employee_id)].copy()
    exc["why"] = np.where(exc.approver_id.isna(), "No approver recorded on grant", "Grantee approved own access")
    return frame("ITGC-UA-01", exc, source_file="user_access_log.csv", source_record_id="grant_id",
                 employee_id="employee_id", system_id="system_id", reference_id="request_ticket",
                 event_date=exc.date_granted, required_by=exc.date_granted, actual_date=pd.NaT,
                 days_late=np.nan, exception_type=exc.why, status="Closed",
                 breach_date=exc.date_granted,
                 detail=exc.access_level + " access on " + exc.system_id + " provisioned " +
                 exc.date_granted.dt.strftime("%Y-%m-%d") + " without approval evidence")


def test_ua02(log, term):
    t = term[in_period(term.termination_date)]
    j = t.merge(log, on="employee_id", how="inner")
    active = j[(j.date_granted <= j.termination_date)
               & (j.access_end_date.isna() | (j.access_end_date >= j.termination_date))].copy()
    POPULATIONS["ITGC-UA-02"] = len(active)
    active["deadline"] = C.add_business_days(active.termination_date, C.TERMINATION_REVOCATION_SLA_BD).values
    measured_to = active.access_end_date.fillna(C.TEST_AS_OF)
    active["bd_elapsed"] = C.business_days_elapsed(active.termination_date, measured_to)
    exc = active[active.access_end_date.isna() | (active.access_end_date > active.deadline)].copy()
    exc["open"] = exc.access_end_date.isna()
    exc["days_late"] = exc.bd_elapsed - C.TERMINATION_REVOCATION_SLA_BD
    return frame("ITGC-UA-02", exc, source_file="termination_log.csv + user_access_log.csv",
                 source_record_id="grant_id", employee_id="employee_id", system_id="system_id",
                 reference_id="request_ticket", event_date=exc.termination_date, required_by=exc.deadline,
                 actual_date=exc.access_end_date, days_late=exc.days_late,
                 exception_type=np.where(exc.open, "Access still active at as-of date", "Access revoked after SLA"),
                 status=np.where(exc.open, "Open", "Closed"),
                 breach_date=exc.deadline + pd.Timedelta(days=1),
                 detail=exc.access_level + " on " + exc.system_id + "; terminated " +
                 exc.termination_date.dt.strftime("%Y-%m-%d") + "; " +
                 np.where(exc.open, "not revoked as of " + C.TEST_AS_OF.strftime("%Y-%m-%d"),
                          "revoked " + exc.access_end_date.dt.strftime("%Y-%m-%d")) +
                 " (" + exc.bd_elapsed.astype(int).astype(str) + " BD)")


def test_ua03(term):
    pop = term[in_period(term.termination_date)].copy()
    POPULATIONS["ITGC-UA-03"] = len(pop)
    pop["bd"] = C.business_days_elapsed(pop.termination_date, pop.hr_notified_date)
    pop["deadline"] = C.add_business_days(pop.termination_date, C.HR_NOTIFICATION_SLA_BD).values
    exc = pop[pop.hr_notified_date.isna() | (pop.hr_notified_date > pop.deadline)].copy()
    return frame("ITGC-UA-03", exc, source_file="termination_log.csv", source_record_id="employee_id",
                 employee_id="employee_id", system_id="All", reference_id="",
                 event_date=exc.termination_date, required_by=exc.deadline, actual_date=exc.hr_notified_date,
                 days_late=exc.bd - C.HR_NOTIFICATION_SLA_BD, exception_type="Late HR separation notice",
                 status="Closed", breach_date=exc.deadline + pd.Timedelta(days=1),
                 detail=exc.termination_type + " termination " + exc.termination_date.dt.strftime("%Y-%m-%d") +
                 "; IT notified " + exc.hr_notified_date.dt.strftime("%Y-%m-%d") +
                 " (" + exc.bd.astype(int).astype(str) + " BD)")


def test_ua04(rev):
    expected = pd.MultiIndex.from_product([list(C.SYSTEMS), ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]],
                                          names=["system_id", "quarter"]).to_frame(index=False)
    POPULATIONS["ITGC-UA-04"] = len(expected)
    j = expected.merge(rev, on=["system_id", "quarter"], how="left", indicator=True)
    missing = j["_merge"] == "left_only"
    late = j.completion_date.isna() | (j.completion_date > j.due_date) | j.reviewer_id.isna()
    exc = j[missing | late].copy()
    exc["why"] = np.select([exc["_merge"] == "left_only", exc.completion_date.isna(), exc.reviewer_id.isna()],
                           ["Review not performed", "Review not completed", "No reviewer recorded"],
                           "Review completed after due date")
    exc["days_late"] = (exc.completion_date - exc.due_date).dt.days
    return frame("ITGC-UA-04", exc, source_file="access_reviews.csv",
                 source_record_id=exc.review_id.fillna("UAR-" + exc.quarter + "-" + exc.system_id),
                 employee_id="reviewer_id", system_id="system_id", reference_id="quarter",
                 event_date=exc.quarter_end, required_by=exc.due_date, actual_date=exc.completion_date,
                 days_late=exc.days_late, exception_type=exc.why, status="Closed",
                 breach_date=exc.due_date + pd.Timedelta(days=1),
                 detail=exc.quarter + " " + exc.system_id + " review due " + exc.due_date.dt.strftime("%Y-%m-%d") +
                 ", completed " + exc.completion_date.dt.strftime("%Y-%m-%d") +
                 " (" + exc.days_late.astype("Int64").astype(str) + " days late)")


# --------------------------------------------------------------- privileged access
def privileged_population(log, appr):
    pop = log[in_period(log.date_granted) & log.access_level.isin(C.PRIVILEGED_ACCESS_LEVELS)]
    return pop.merge(appr.add_prefix("appr_").rename(columns={"appr_request_ticket": "request_ticket"}),
                     on="request_ticket", how="left")


def test_pa01(log, appr):
    j = privileged_population(log, appr)
    POPULATIONS["ITGC-PA-01"] = len(j)
    checks = {
        "No approval record in register": j.appr_approval_id.isna(),
        "Approval is for a different employee": j.appr_approval_id.notna() & (j.appr_employee_id != j.employee_id),
        "Approval is for a different system": j.appr_approval_id.notna() & (j.appr_system_id != j.system_id),
        "Granted level differs from approved level": j.appr_approval_id.notna() & (j.appr_access_level_approved != j.access_level),
        "Approved after access was granted": j.appr_approval_date > j.date_granted,
    }
    reasons = pd.DataFrame(checks)
    j["why"] = reasons.apply(lambda r: "; ".join(k for k, v in r.items() if v), axis=1)
    exc = j[reasons.any(axis=1)].copy()
    return frame("ITGC-PA-01", exc, source_file="user_access_log.csv + privileged_access_approvals.csv",
                 source_record_id="grant_id", employee_id="employee_id", system_id="system_id",
                 reference_id="request_ticket", event_date=exc.date_granted, required_by=exc.date_granted,
                 actual_date=exc.appr_approval_date, days_late=(exc.appr_approval_date - exc.date_granted).dt.days,
                 exception_type=exc.why, status=np.where(exc.access_end_date.isna(), "Open", "Closed"),
                 breach_date=exc.date_granted,
                 detail=exc.access_level + " on " + exc.system_id + " granted " + exc.date_granted.dt.strftime("%Y-%m-%d") +
                 "; register: " + exc.appr_approval_id.fillna("none") + " / " +
                 exc.appr_access_level_approved.fillna("-") + " / " + exc.appr_system_id.fillna("-"))


def test_pa02(log, appr):
    j = privileged_population(log, appr)
    j = j[j.appr_approval_id.notna()]
    POPULATIONS["ITGC-PA-02"] = len(j)
    exc = j[j.appr_approver_id == j.employee_id].copy()
    return frame("ITGC-PA-02", exc, source_file="privileged_access_approvals.csv",
                 source_record_id="grant_id", employee_id="employee_id", system_id="system_id",
                 reference_id="appr_approval_id", event_date=exc.appr_approval_date, required_by=pd.NaT,
                 actual_date=exc.date_granted, days_late=np.nan, exception_type="Self-approved privileged access",
                 status=np.where(exc.access_end_date.isna(), "Open", "Closed"), breach_date=exc.date_granted,
                 detail=exc.employee_id + " approved own " + exc.access_level + " request on " + exc.system_id +
                 " (" + exc.appr_approval_id + ")")


# --------------------------------------------------------------- change management
def change_population(chg):
    return chg[in_period(chg.implementation_date)].copy()


def test_cm01(chg):
    pop = change_population(chg)
    POPULATIONS["ITGC-CM-01"] = len(pop)
    emergency = pop.change_type.eq("Emergency")
    missing = pop.approved_by.isna() | pop.approval_date.isna()
    pop["bd_after"] = C.business_days_elapsed(pop.implementation_date, pop.approval_date)
    late_normal = ~emergency & ~missing & (pop.approval_date > pop.implementation_date)
    retro_deadline = C.add_business_days(pop.implementation_date, C.EMERGENCY_RETRO_APPROVAL_BD).values
    late_emerg = emergency & ~missing & (pop.approval_date.dt.normalize() > retro_deadline)
    exc = pop[missing | late_normal | late_emerg].copy()
    exc["why"] = np.select([missing[exc.index], late_normal[exc.index]],
                           ["No approver / approval date recorded", "Approved after implementation"],
                           "Emergency change approved outside 2-BD window")
    required = np.where(exc.change_type.eq("Emergency"),
                        C.add_business_days(exc.implementation_date, C.EMERGENCY_RETRO_APPROVAL_BD).values,
                        exc.implementation_date.values)
    return frame("ITGC-CM-01", exc, source_file="change_log.csv", source_record_id="change_id",
                 employee_id="requested_by", system_id="system_id", reference_id="change_type",
                 event_date=exc.implementation_date, required_by=pd.to_datetime(required),
                 actual_date=exc.approval_date,
                 days_late=np.where(exc.change_type.eq("Emergency"), exc.bd_after - C.EMERGENCY_RETRO_APPROVAL_BD,
                                    (exc.approval_date - exc.implementation_date).dt.days),
                 exception_type=exc.why, status="Closed", breach_date=exc.implementation_date.dt.normalize(),
                 detail=exc.change_type + " change '" + exc.description + "' implemented " +
                 exc.implementation_date.dt.strftime("%Y-%m-%d %H:%M") + "; " +
                 np.where(exc.approval_date.isna(), "no approval recorded",
                          "approved " + exc.approval_date.dt.strftime("%Y-%m-%d %H:%M") + " by " + exc.approved_by.fillna("-")))


def test_cm02(chg):
    pop = change_population(chg)
    POPULATIONS["ITGC-CM-02"] = len(pop)
    flag = pop.rollback_plan.astype(str).str.strip().str.upper()
    exc = pop[~flag.isin(["YES", "Y"])].copy()
    return frame("ITGC-CM-02", exc, source_file="change_log.csv", source_record_id="change_id",
                 employee_id="requested_by", system_id="system_id", reference_id="change_type",
                 event_date=exc.implementation_date, required_by=exc.implementation_date, actual_date=pd.NaT,
                 days_late=np.nan, exception_type="No documented rollback plan", status="Closed",
                 breach_date=exc.implementation_date.dt.normalize(),
                 detail=exc.change_type + " change '" + exc.description + "' rollback_plan='" + exc.rollback_plan + "'")


def test_cm03(chg):
    pop = change_population(chg)
    pop = pop[pop.approved_by.notna()]
    POPULATIONS["ITGC-CM-03"] = len(pop)
    exc = pop[pop.approved_by == pop.requested_by].copy()
    return frame("ITGC-CM-03", exc, source_file="change_log.csv", source_record_id="change_id",
                 employee_id="requested_by", system_id="system_id", reference_id="change_type",
                 event_date=exc.implementation_date, required_by=pd.NaT, actual_date=exc.approval_date,
                 days_late=np.nan, exception_type="Requester approved own change", status="Closed",
                 breach_date=exc.implementation_date.dt.normalize(),
                 detail=exc.requested_by + " requested and approved '" + exc.description + "'")


# --------------------------------------------------------------- prioritization + outputs
def prioritize(exc: pd.DataFrame) -> pd.DataFrame:
    exc["risk_id"] = exc.control_id.map(lambda c: control_by_id(c)["risk_id"])
    exc["severity_score"] = exc.risk_id.map(lambda r: severity(risk_by_id(r))[0])
    exc["exception_age_days"] = (C.TEST_AS_OF - pd.to_datetime(exc.breach_date)).dt.days.clip(lower=0)
    age_factor = 1 + exc.exception_age_days.clip(upper=365) / 182.5       # 1.0 (new) - 3.0 (1 yr+)
    exc["priority_score"] = (exc.severity_score * age_factor + np.where(exc.status == "Open", 10, 0)).round(1)
    exc["priority_tier"] = pd.cut(exc.priority_score, [-1, 20, 35, 50, 1e9],
                                  labels=["Low", "Medium", "High", "Critical"]).astype(str)
    return exc


def conclude(rate: float, n_exc: int, sev_rating: str) -> tuple[str, str]:
    if n_exc == 0:
        return "Effective", "No exceptions noted"
    if sev_rating in ("Critical", "High") and rate >= 0.05:
        return "Exception Noted", "Deficiency - evaluate for significant deficiency (aggregation & compensating controls)"
    return "Exception Noted", "Control deficiency"


def main():
    log, term, appr, rev, chg = load()
    results = [test_ua01(log), test_ua02(log, term), test_ua03(term), test_ua04(rev),
               test_pa01(log, appr), test_pa02(log, appr), test_cm01(chg), test_cm02(chg), test_cm03(chg)]
    allx = pd.concat([r for r in results if len(r)], ignore_index=True)
    allx = prioritize(allx)
    allx.insert(1, "exception_id", allx.groupby("control_id").cumcount().add(1)
                .map("{:03d}".format).radd(allx.control_id.str.replace("ITGC-", "EX-") + "-"))
    for col in ["event_date", "required_by", "actual_date", "breach_date"]:
        allx[col] = pd.to_datetime(allx[col]).dt.strftime("%Y-%m-%d").fillna("")

    C.EXCEPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for c in CONTROLS:
        cid = c["control_id"]
        x = allx[allx.control_id == cid]
        x.to_csv(C.EXCEPTIONS_DIR / f"{cid}_exceptions.csv", index=False)
        pop = POPULATIONS[cid]
        score, rating = severity(risk_by_id(c["risk_id"]))
        concl, deficiency = conclude(len(x) / pop if pop else 0, len(x), rating)
        summary.append(dict(control_id=cid, domain=c["domain"], title=c["title"], risk_id=c["risk_id"],
                            risk_severity_score=score, risk_rating=rating, control_type=c["type"],
                            frequency=c["frequency"], population=pop, exceptions=len(x),
                            unique_employees=x.employee_id.nunique() if len(x) else 0,
                            exception_rate=round(len(x) / pop, 4) if pop else 0,
                            open_exceptions=int((x.status == "Open").sum()),
                            median_age_days=float(x.exception_age_days.median()) if len(x) else 0,
                            max_priority_score=float(x.priority_score.max()) if len(x) else 0,
                            conclusion=concl, deficiency_assessment=deficiency))
    summary = pd.DataFrame(summary)
    allx.to_csv(C.EXCEPTIONS_DIR / "all_exceptions.csv", index=False)
    summary.to_csv(C.OUTPUT_DIR / "test_results_summary.csv", index=False)

    with pd.ExcelWriter(C.OUTPUT_DIR / "ITGC_Testing_Results.xlsx", engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False)
        allx.sort_values("priority_score", ascending=False).to_excel(xw, sheet_name="Remediation Priority", index=False)
        for cid in summary.control_id:
            allx[allx.control_id == cid].to_excel(xw, sheet_name=cid.replace("ITGC-", ""), index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(
                    60, max(10, max(len(str(v.value or "")) for v in col[:50]) + 2))
            ws.freeze_panes = "A2"

    print("[Phase 3] pandas control testing complete")
    print(summary[["control_id", "population", "exceptions", "exception_rate", "conclusion"]].to_string(index=False))


if __name__ == "__main__":
    main()
