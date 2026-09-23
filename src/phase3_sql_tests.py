"""Phase 3 (SQL) - run sql/*.sql against a SQLite copy of the populations and
reconcile the SQL exception set to the pandas exception set record-by-record.

Two independent implementations agreeing is the analytics equivalent of a
reperformance check on the testing logic itself.
"""
import sqlite3

import pandas as pd

import common as C

SQL_FILES = {
    "ITGC-UA-01": "ua01_new_access_approval.sql",
    "ITGC-UA-02": "ua02_termination_revocation.sql",
    "ITGC-UA-03": "ua03_hr_notification.sql",
    "ITGC-UA-04": "ua04_access_review.sql",
    "ITGC-PA-01": "pa01_privileged_authorization.sql",
    "ITGC-PA-02": "pa02_privileged_sod.sql",
    "ITGC-CM-01": "cm01_change_approval.sql",
    "ITGC-CM-02": "cm02_rollback_plan.sql",
    "ITGC-CM-03": "cm03_change_sod.sql",
}


def build_db(path):
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    for name in ["user_access_log", "termination_log", "privileged_access_approvals",
                 "access_reviews", "change_log", "employees"]:
        pd.read_csv(C.DATA_DIR / f"{name}.csv", dtype=str).to_sql(name, con, index=False)
    days = pd.date_range("2024-12-01", "2026-03-31")
    busday = {d: C.is_business_day(d) for d in days}
    pd.DataFrame({"cal_date": days.strftime("%Y-%m-%d"),
                  "is_business_day": [int(busday[d]) for d in days]}).to_sql("dim_date", con, index=False)
    pd.DataFrame({"access_level": C.PRIVILEGED_ACCESS_LEVELS}).to_sql("privileged_levels", con, index=False)
    pd.DataFrame({"system_id": list(C.SYSTEMS), "system_name": list(C.SYSTEMS.values())}).to_sql("systems", con, index=False)
    return con


def main():
    con = build_db(C.OUTPUT_DIR / "itgc_testing.sqlite")
    params = dict(period_start=C.PERIOD_START.strftime("%Y-%m-%d"), period_end=C.PERIOD_END.strftime("%Y-%m-%d"),
                  as_of=C.TEST_AS_OF.strftime("%Y-%m-%d"), termination_sla_bd=C.TERMINATION_REVOCATION_SLA_BD,
                  hr_sla_bd=C.HR_NOTIFICATION_SLA_BD, emergency_bd=C.EMERGENCY_RETRO_APPROVAL_BD)
    pandas_exc = pd.read_csv(C.EXCEPTIONS_DIR / "all_exceptions.csv", dtype=str)
    out_dir = C.EXCEPTIONS_DIR / "sql"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for cid, fname in SQL_FILES.items():
        sql = (C.SQL_DIR / fname).read_text()
        res = pd.read_sql_query(sql, con, params=params)
        res.to_csv(out_dir / f"{cid}_sql.csv", index=False)
        s = set(res.source_record_id)
        p = set(pandas_exc.loc[pandas_exc.control_id == cid, "source_record_id"])
        rows.append(dict(control_id=cid, sql_file=f"sql/{fname}", sql_exceptions=len(s), pandas_exceptions=len(p),
                         only_in_sql=len(s - p), only_in_pandas=len(p - s), agree=s == p))
    rec = pd.DataFrame(rows)
    rec.to_csv(C.OUTPUT_DIR / "sql_vs_pandas_reconciliation.csv", index=False)
    print("[Phase 3] SQL tests vs pandas tests")
    print(rec.to_string(index=False))
    if not rec.agree.all():
        raise SystemExit("SQL and pandas results disagree - investigate before relying on results")


if __name__ == "__main__":
    main()
