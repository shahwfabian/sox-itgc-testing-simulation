"""Phase 2 - generate synthetic ITGC populations with a seeded exception rate.

Outputs (data/):   employees, user_access_log, termination_log,
                   privileged_access_approvals, access_reviews, change_log
Answer key:        answer_key/seeded_exceptions.csv  (Phase 3 never reads this)

The data deliberately includes "near misses" that are NOT exceptions - revocation
on exactly the 5th business day, Friday terminations revoked on Monday, emergency
changes approved retrospectively inside policy, same-day approvals made hours
before implementation, "Y"/"yes" spellings of the rollback flag - so the tests
have to apply the policy correctly rather than just pattern-match.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import common as C

rng = np.random.default_rng(C.RANDOM_SEED)
answer_key: list[dict] = []

FIRST = ["Avery", "Jordan", "Priya", "Marcus", "Elena", "Wei", "Fatima", "Diego", "Hannah", "Kwame",
         "Sofia", "Liam", "Aisha", "Noah", "Mei", "Omar", "Grace", "Ravi", "Chloe", "Mateo",
         "Nadia", "Ethan", "Yuki", "Isaac", "Leila", "Samuel", "Zara", "Lucas", "Amara", "Owen"]
LAST = ["Okafor", "Chen", "Patel", "Rivera", "Novak", "Kim", "Haddad", "Silva", "Brennan", "Mensah",
        "Kowalski", "Nguyen", "Ferreira", "Johansson", "Adeyemi", "Morales", "Tanaka", "Reyes",
        "Schultz", "Osei", "Duarte", "Iqbal", "Larsen", "Moreau", "Abara", "Walsh", "Castillo", "Singh"]
DEPTS = {  # department -> (weight, typical titles)
    "Finance & Accounting": (0.22, ["Staff Accountant", "Senior Accountant", "GL Analyst", "Controller"]),
    "Lending Operations": (0.24, ["Loan Processor", "Loan Servicing Specialist", "Underwriter"]),
    "Treasury": (0.08, ["Treasury Analyst", "Cash Manager"]),
    "Customer Operations": (0.20, ["Operations Associate", "Client Service Rep"]),
    "Risk & Compliance": (0.08, ["Compliance Analyst", "Risk Analyst"]),
    "Information Technology": (0.18, ["Software Engineer", "Systems Administrator", "Database Administrator",
                                      "Release Engineer", "IT Support Analyst"]),
}
DEPT_SYSTEMS = {
    "Finance & Accounting": ["GL01", "FCR", "TMS"],
    "Lending Operations": ["LSP", "GL01"],
    "Treasury": ["TMS", "GL01"],
    "Customer Operations": ["LSP"],
    "Risk & Compliance": ["GL01", "LSP", "FCR"],
    "Information Technology": ["GL01", "LSP", "TMS", "FCR"],
}


def rand_bday(start: pd.Timestamp, end: pd.Timestamp) -> pd.Timestamp:
    while True:
        d = start + pd.Timedelta(days=int(rng.integers(0, (end - start).days + 1)))
        if C.is_business_day(d):
            return d


def add_bd(d: pd.Timestamp, n: int) -> pd.Timestamp:
    return C.add_business_days([d], n).iloc[0]


def seed(control_id, source_file, record_key, exception_type, detail):
    answer_key.append(dict(control_id=control_id, source_file=source_file, record_key=record_key,
                           exception_type=exception_type, detail=detail))


# ------------------------------------------------------------------ employees
def make_employees(n=1250) -> pd.DataFrame:
    depts = list(DEPTS)
    weights = np.array([DEPTS[d][0] for d in depts])
    rows = []
    for i in range(n):
        dept = depts[rng.choice(len(depts), p=weights / weights.sum())]
        # ~10% hired during the audit period
        if rng.random() < 0.10:
            hire = rand_bday(C.PERIOD_START, pd.Timestamp("2025-11-28"))
        else:
            hire = rand_bday(pd.Timestamp("2012-01-02"), pd.Timestamp("2024-12-20"))
        rows.append(dict(employee_id=f"E{10001 + i}",
                         name=f"{FIRST[rng.integers(len(FIRST))]} {LAST[rng.integers(len(LAST))]}",
                         department=dept, job_title=str(rng.choice(DEPTS[dept][1])), hire_date=hire))
    emp = pd.DataFrame(rows)
    emp["role_group"] = "Staff"
    return emp


def assign_roles(emp: pd.DataFrame) -> dict:
    """Carve out approver populations (never terminated, never approve themselves)."""
    tenured = emp[emp.hire_date < pd.Timestamp("2022-01-01")]
    it = tenured[tenured.department == "Information Technology"]
    non_it = tenured[tenured.department != "Information Technology"]
    roles = {
        "managers": list(non_it.sample(70, random_state=1).employee_id),
        "system_owners": {s: e for s, e in zip(C.SYSTEMS, non_it.drop(non_it.sample(70, random_state=1).index)
                                               .sample(4, random_state=2).employee_id)},
        "infosec": list(it.sample(5, random_state=3).employee_id),
        "cab": list(it.drop(it.sample(5, random_state=3).index).sample(6, random_state=4).employee_id),
    }
    used = set(roles["managers"]) | set(roles["system_owners"].values()) | set(roles["infosec"]) | set(roles["cab"])
    it_rest = emp[(emp.department == "Information Technology") & ~emp.employee_id.isin(used)]
    roles["developers"] = list(it_rest[it_rest.job_title == "Software Engineer"].employee_id)
    roles["release_eng"] = list(it_rest[it_rest.job_title.isin(["Release Engineer", "Systems Administrator"])].employee_id)
    roles["priv_users"] = list(it_rest[it_rest.job_title.isin(["Systems Administrator", "Database Administrator",
                                                                "Release Engineer"])].employee_id)
    roles["protected"] = used
    for col, ids in [("Manager", roles["managers"]), ("System Owner", roles["system_owners"].values()),
                     ("Information Security", roles["infosec"]), ("CAB Member", roles["cab"])]:
        emp.loc[emp.employee_id.isin(list(ids)), "role_group"] = col
    return roles


# ------------------------------------------------------------------ terminations
def make_terminations(emp, roles, n=185) -> pd.DataFrame:
    pool = emp[~emp.employee_id.isin(roles["protected"])]
    picked = pool.sample(n, random_state=5)
    rows = []
    for _, e in picked.iterrows():
        earliest = max(C.PERIOD_START, e.hire_date + pd.Timedelta(days=45))
        term = rand_bday(earliest, pd.Timestamp("2025-12-19"))
        lag = 0 if rng.random() < 0.72 else 1
        rows.append(dict(employee_id=e.employee_id, termination_date=term,
                         termination_type=str(rng.choice(["Voluntary", "Involuntary"], p=[0.78, 0.22])),
                         hr_notified_date=add_bd(term, lag)))
    term = pd.DataFrame(rows).sort_values("termination_date").reset_index(drop=True)

    # Seed UA-03: HR notified IT late (2-9 business days)
    late = term.sample(11, random_state=6).index
    for i in late:
        lag = int(rng.integers(2, 10))
        term.loc[i, "hr_notified_date"] = add_bd(term.loc[i, "termination_date"], lag)
        seed("ITGC-UA-03", "termination_log.csv", term.loc[i, "employee_id"], "Late HR notification",
             f"HR notified IT {lag} business days after termination")
    return term, set(late)


# ------------------------------------------------------------------ access log
def make_access_log(emp, roles, term):
    term_by_emp = term.set_index("employee_id").termination_date.to_dict()
    mgr = roles["managers"]
    rows, tix = [], iter(range(100001, 999999))

    def grant(e, system, level, when, approver):
        rows.append(dict(grant_id=None, employee_id=e, system_id=system, access_level=level,
                         request_ticket=f"RITM{next(tix)}", date_granted=when, approver_id=approver,
                         access_end_date=pd.NaT))

    for _, e in emp.iterrows():
        systems = DEPT_SYSTEMS[e.department]
        k = int(rng.integers(1, min(3, len(systems)) + 1))
        for s in rng.choice(systems, size=k, replace=False):
            level = str(rng.choice(C.STANDARD_ACCESS_LEVELS, p=[0.25, 0.6, 0.15]))
            when = add_bd(e.hire_date, int(rng.integers(0, 4)))
            grant(e.employee_id, str(s), level, when, str(rng.choice([m for m in mgr if m != e.employee_id])))
        # in-period access modifications for ~25% of staff
        if rng.random() < 0.25:
            s = str(rng.choice(systems))
            last = term_by_emp.get(e.employee_id, pd.Timestamp("2025-12-19")) - pd.Timedelta(days=10)
            start = max(C.PERIOD_START, e.hire_date + pd.Timedelta(days=20))
            if start < last:
                grant(e.employee_id, s, str(rng.choice(C.STANDARD_ACCESS_LEVELS)), rand_bday(start, last),
                      str(rng.choice([m for m in mgr if m != e.employee_id])))

    # privileged grants: standing admin access + time-bound elevated ("firefighter") access
    approvals = []
    infosec = roles["infosec"]
    for e in roles["priv_users"]:
        hire = emp.set_index("employee_id").hire_date[e]
        last = term_by_emp.get(e, pd.Timestamp("2025-12-19")) - pd.Timedelta(days=10)
        n_grants = int(rng.integers(1, 5))
        for j in range(n_grants):
            s = str(rng.choice(list(C.SYSTEMS)))
            level = str(rng.choice(C.PRIVILEGED_ACCESS_LEVELS, p=[0.45, 0.25, 0.30]))
            in_period = j > 0 or rng.random() < 0.6
            start = max(C.PERIOD_START, hire + pd.Timedelta(days=20)) if in_period else hire + pd.Timedelta(days=30)
            end = last if in_period else pd.Timestamp("2024-12-20")
            if start >= end:
                continue
            when = rand_bday(start, end)
            approver = str(rng.choice([a for a in infosec if a != e]))
            grant(e, s, level, when, approver)
            appr_date = when - pd.Timedelta(days=int(rng.integers(0, 4)))
            approvals.append(dict(request_ticket=rows[-1]["request_ticket"], employee_id=e, system_id=s,
                                  access_level_approved=level, approver_id=approver,
                                  approver_role="Information Security Manager", approval_date=appr_date))
            if in_period and rng.random() < 0.55:  # firefighter access auto-expires after 1-5 days
                rows[-1]["access_end_date"] = add_bd(when, int(rng.integers(1, 6)))

    log = pd.DataFrame(rows).sort_values(["date_granted", "employee_id"]).reset_index(drop=True)
    log["grant_id"] = [f"G{200001 + i}" for i in range(len(log))]
    appr = pd.DataFrame(approvals)
    return log, appr


def apply_role_changes(log, term):
    """Some non-terminated users lose access on role change (noise, not exceptions)."""
    termed = set(term.employee_id)
    cand = log[~log.employee_id.isin(termed) & log.access_end_date.isna()
               & ~log.access_level.isin(C.PRIVILEGED_ACCESS_LEVELS)]
    for i in cand.sample(frac=0.07, random_state=7).index:
        start = max(log.loc[i, "date_granted"] + pd.Timedelta(days=30), C.PERIOD_START)
        if start < pd.Timestamp("2025-12-15"):
            log.loc[i, "access_end_date"] = rand_bday(start, pd.Timestamp("2025-12-15"))


def apply_terminations(log, term, late_hr):
    """Revoke terminated users' access - mostly within SLA, some seeded late / never."""
    term_idx = term.set_index("employee_id")
    termed = list(term.employee_id)
    # 14 employees (~7.6%) with at least one grant not revoked within SLA;
    # late-HR employees are over-represented (a realistic root cause).
    late_hr_ids = list(term.loc[list(late_hr), "employee_id"])
    late_emps = list(rng.choice(late_hr_ids, 6, replace=False)) + \
        list(rng.choice([e for e in termed if e not in late_hr_ids], 8, replace=False))
    still_active = set(late_emps[:2] + late_emps[6:9])  # 5 never revoked at all
    for e in termed:
        t = term_idx.termination_date[e]
        active = log[(log.employee_id == e) & (log.date_granted <= t)
                     & (log.access_end_date.isna() | (log.access_end_date > t))].index
        if len(active) == 0:
            continue
        # target grants for seeded employees: one grant (or all grants for still-active ones)
        bad = set(active) if e in still_active else {int(rng.choice(active))} if e in late_emps else set()
        for i in active:
            if i in bad:
                if e in still_active:
                    log.loc[i, "access_end_date"] = pd.NaT
                    seed("ITGC-UA-02", "user_access_log.csv", log.loc[i, "grant_id"], "Access never revoked",
                         f"{e} terminated {t:%Y-%m-%d}; {log.loc[i, 'system_id']} access still active")
                else:
                    lag = int(rng.integers(6, 23))
                    log.loc[i, "access_end_date"] = add_bd(t, lag)
                    seed("ITGC-UA-02", "user_access_log.csv", log.loc[i, "grant_id"], "Late revocation",
                         f"{e} terminated {t:%Y-%m-%d}; {log.loc[i, 'system_id']} revoked {lag} BD later")
            else:
                # compliant: 0-5 BD, including some exactly on the 5th business day
                lag = int(rng.choice([0, 1, 1, 2, 2, 3, 4, 5]))
                log.loc[i, "access_end_date"] = add_bd(t, lag)


def seed_access_approvals(log, appr, roles):
    in_period = log.date_granted.between(C.PERIOD_START, C.PERIOD_END)
    # UA-01: 28 in-period standard grants provisioned without an approver
    std = log[in_period & log.access_level.isin(C.STANDARD_ACCESS_LEVELS)]
    for i in std.sample(28, random_state=8).index:
        log.loc[i, "approver_id"] = np.nan
        seed("ITGC-UA-01", "user_access_log.csv", log.loc[i, "grant_id"], "Missing approver",
             f"{log.loc[i, 'access_level']} on {log.loc[i, 'system_id']} provisioned with no approver")

    priv = log[in_period & log.access_level.isin(C.PRIVILEGED_ACCESS_LEVELS)]
    picks = list(priv.sample(13, random_state=9).index)
    appr = appr.set_index("request_ticket")
    # PA-01 (a): 5 grants with no approval record at all (log still shows an approver!)
    for i in picks[:5]:
        appr = appr.drop(log.loc[i, "request_ticket"])
        seed("ITGC-PA-01", "user_access_log.csv", log.loc[i, "grant_id"], "No approval record",
             f"Ticket {log.loc[i, 'request_ticket']} not in approval register")
    # PA-01 (b): 2 approved after access was granted
    for i in picks[5:7]:
        t = log.loc[i, "request_ticket"]
        lag = int(rng.integers(2, 12))
        appr.loc[t, "approval_date"] = log.loc[i, "date_granted"] + pd.Timedelta(days=lag)
        seed("ITGC-PA-01", "user_access_log.csv", log.loc[i, "grant_id"], "Approval after grant",
             f"Approved {lag} days after access granted")
    # PA-01 (c): 2 approved for a different (lower-risk) privileged level; 1 for a different system
    for i in picks[7:9]:
        t = log.loc[i, "request_ticket"]
        other = [l for l in C.PRIVILEGED_ACCESS_LEVELS if l != log.loc[i, "access_level"]]
        appr.loc[t, "access_level_approved"] = str(rng.choice(other))
        seed("ITGC-PA-01", "user_access_log.csv", log.loc[i, "grant_id"], "Access level mismatch",
             f"Granted {log.loc[i, 'access_level']} but approved {appr.loc[t, 'access_level_approved']}")
    i = picks[9]
    t = log.loc[i, "request_ticket"]
    appr.loc[t, "system_id"] = str(rng.choice([s for s in C.SYSTEMS if s != log.loc[i, "system_id"]]))
    seed("ITGC-PA-01", "user_access_log.csv", log.loc[i, "grant_id"], "System mismatch",
         f"Granted on {log.loc[i, 'system_id']} but approval is for {appr.loc[t, 'system_id']}")
    # PA-02: no self-approvals seeded - the workflow block operated (control expected effective)
    appr = appr.reset_index()
    # noise: approvals for requests later cancelled (never provisioned) - not exceptions
    for k in range(4):
        e = str(rng.choice(roles["priv_users"]))
        appr.loc[len(appr)] = dict(request_ticket=f"RITM{990001 + k}", employee_id=e,
                                   system_id=str(rng.choice(list(C.SYSTEMS))),
                                   access_level_approved="Administrator",
                                   approver_id=str(rng.choice(roles["infosec"])),
                                   approver_role="Information Security Manager",
                                   approval_date=rand_bday(C.PERIOD_START, C.PERIOD_END))
    appr = appr.sort_values("approval_date").reset_index(drop=True)
    appr.insert(0, "approval_id", [f"PA{50001 + i}" for i in range(len(appr))])
    return appr


# ------------------------------------------------------------------ access reviews
def make_access_reviews(log, roles):
    rows = []
    for q, qe in enumerate(pd.to_datetime(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]), 1):
        due = qe + pd.Timedelta(days=C.ACCESS_REVIEW_DUE_DAYS)
        for s in C.SYSTEMS:
            active = log[(log.system_id == s) & (log.date_granted <= qe)
                         & (log.access_end_date.isna() | (log.access_end_date > qe))]
            removals = int(rng.integers(0, max(2, len(active) // 60)))
            done = due - pd.Timedelta(days=int(rng.integers(1, 20)))
            rows.append(dict(review_id=f"UAR-2025Q{q}-{s}", system_id=s, quarter=f"2025-Q{q}",
                             quarter_end=qe, due_date=due, reviewer_id=roles["system_owners"][s],
                             accounts_in_scope=len(active),
                             privileged_accounts_in_scope=int(active.access_level.isin(C.PRIVILEGED_ACCESS_LEVELS).sum()),
                             removals_requested=removals, completion_date=done))
    rev = pd.DataFrame(rows)
    i = rev.index[rev.review_id == "UAR-2025Q3-LSP"][0]
    rev.loc[i, "completion_date"] = rev.loc[i, "due_date"] + pd.Timedelta(days=12)
    seed("ITGC-UA-04", "access_reviews.csv", "UAR-2025Q3-LSP", "Review completed late",
         "Q3 LSP review signed off 12 days after due date")
    return rev


# ------------------------------------------------------------------ change log
TEMPLATES = {
    "GL01": ["Update journal entry upload template validation", "Patch GL posting batch job",
             "Add new cost center hierarchy", "Modify intercompany elimination rule",
             "Upgrade GL reporting module", "Fix FX revaluation rounding"],
    "LSP": ["Adjust interest accrual calculation for ARM loans", "Deploy payment posting hotfix",
            "Update delinquency aging buckets", "Change escrow disbursement interface",
            "Modify loan boarding field mapping", "Upgrade servicing platform minor release"],
    "TMS": ["Update bank statement import parser", "Modify cash positioning report",
            "Patch wire approval workflow", "Add new counterparty limit fields"],
    "FCR": ["Update consolidation mapping for new entity", "Modify close checklist automation",
            "Patch eliminations report", "Update XBRL tagging template"],
}


def make_changes(roles, n=620):
    rows = []
    devs, cab, rel = roles["developers"], roles["cab"], roles["release_eng"]
    for i in range(n):
        s = str(rng.choice(list(C.SYSTEMS), p=[0.32, 0.36, 0.14, 0.18]))
        ctype = str(rng.choice(["Standard", "Normal", "Emergency"], p=[0.25, 0.65, 0.10]))
        impl_day = rand_bday(C.PERIOD_START + pd.Timedelta(days=7), C.PERIOD_END)
        if ctype == "Emergency" and rng.random() < 0.3:
            impl_day = impl_day + pd.Timedelta(days=int(rng.integers(0, 2)))  # may fall on weekend
        impl = impl_day + pd.Timedelta(hours=int(rng.integers(18, 23)), minutes=int(rng.choice([0, 15, 30, 45])))
        if ctype == "Emergency" and rng.random() < 0.6:
            # retrospective approval within policy (0-2 BD after implementation)
            appr_day = add_bd(impl_day, int(rng.integers(0, 3))) if C.is_business_day(impl_day) \
                else add_bd(impl_day, int(rng.integers(0, 2)))
            appr = appr_day + pd.Timedelta(hours=int(rng.integers(9, 17)))
            if appr_day == impl_day:
                appr = impl + pd.Timedelta(hours=1)
        elif rng.random() < 0.12:
            appr = impl_day + pd.Timedelta(hours=int(rng.integers(9, 15)))  # same-day, before 6pm deploy
        else:
            appr = add_bd(impl_day, -int(rng.integers(1, 11))) + pd.Timedelta(hours=int(rng.integers(9, 17)))
        req = str(rng.choice(devs))
        rows.append(dict(change_id=f"CHG{30001 + i:07d}", system_id=s, change_type=ctype,
                         description=str(rng.choice(TEMPLATES[s])), requested_by=req,
                         approved_by=str(rng.choice(cab)), approval_date=appr,
                         implementation_date=impl, implemented_by=str(rng.choice(rel)),
                         rollback_plan=str(rng.choice(["Yes", "Yes", "Yes", "Y", "yes"])),
                         status=str(rng.choice(["Closed - Successful"] * 12 + ["Closed - Rolled Back"]))))
    chg = pd.DataFrame(rows).sort_values("implementation_date").reset_index(drop=True)
    chg["change_id"] = [f"CHG{30001 + i:07d}" for i in range(len(chg))]

    idx = list(chg.sample(75, random_state=11).index)
    normal = [i for i in idx if chg.loc[i, "change_type"] != "Emergency"]
    emerg_all = list(chg[chg.change_type == "Emergency"].index)
    emerg = [i for i in rng.choice(emerg_all, 6, replace=False) if i not in idx]
    # CM-01 (a) 10 missing approver
    for i in normal[:10]:
        chg.loc[i, ["approved_by", "approval_date"]] = [np.nan, pd.NaT]
        seed("ITGC-CM-01", "change_log.csv", chg.loc[i, "change_id"], "Missing approver", "No approver or approval date")
    # CM-01 (b) 16 normal/standard changes approved after implementation
    for i in normal[10:26]:
        lag = int(rng.integers(1, 11))
        chg.loc[i, "approval_date"] = chg.loc[i, "implementation_date"] + pd.Timedelta(days=lag, hours=-6)
        seed("ITGC-CM-01", "change_log.csv", chg.loc[i, "change_id"], "Approved after implementation",
             f"{chg.loc[i, 'change_type']} change approved ~{lag} days after go-live")
    # CM-01 (c) emergency changes approved outside the 2-BD retrospective window
    for i in emerg:
        lag = int(rng.integers(3, 10))
        chg.loc[i, "approval_date"] = add_bd(chg.loc[i, "implementation_date"].normalize(), lag) + pd.Timedelta(hours=11)
        seed("ITGC-CM-01", "change_log.csv", chg.loc[i, "change_id"], "Emergency approval outside window",
             f"Emergency change approved {lag} business days after implementation")
    # CM-02: 22 changes with no rollback plan
    for i in normal[26:48]:
        chg.loc[i, "rollback_plan"] = str(rng.choice(["No", "No", "N"]))
        seed("ITGC-CM-02", "change_log.csv", chg.loc[i, "change_id"], "No rollback plan",
             "Change record has no documented back-out plan")
    # CM-03: no self-approvals seeded (control expected effective)
    return chg


# ------------------------------------------------------------------ main
def fmt_dates(df, cols, ts=False):
    for c in cols:
        df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d %H:%M" if ts else "%Y-%m-%d")
    return df


def main():
    emp = make_employees()
    roles = assign_roles(emp)
    term, late_hr = make_terminations(emp, roles)
    log, appr = make_access_log(emp, roles, term)
    apply_role_changes(log, term)
    apply_terminations(log, term, late_hr)
    appr = seed_access_approvals(log, appr, roles)
    reviews = make_access_reviews(log, roles)
    changes = make_changes(roles)

    C.DATA_DIR.mkdir(exist_ok=True)
    C.ANSWER_KEY_DIR.mkdir(exist_ok=True)
    fmt_dates(emp, ["hire_date"]).to_csv(C.DATA_DIR / "employees.csv", index=False)
    fmt_dates(log, ["date_granted", "access_end_date"]).to_csv(C.DATA_DIR / "user_access_log.csv", index=False)
    fmt_dates(term, ["termination_date", "hr_notified_date"]).to_csv(C.DATA_DIR / "termination_log.csv", index=False)
    fmt_dates(appr, ["approval_date"]).to_csv(C.DATA_DIR / "privileged_access_approvals.csv", index=False)
    fmt_dates(reviews, ["quarter_end", "due_date", "completion_date"]).to_csv(C.DATA_DIR / "access_reviews.csv", index=False)
    fmt_dates(changes, ["approval_date", "implementation_date"], ts=True).to_csv(C.DATA_DIR / "change_log.csv", index=False)

    ak = pd.DataFrame(answer_key)
    ak.to_csv(C.ANSWER_KEY_DIR / "seeded_exceptions.csv", index=False)
    print(f"[Phase 2] employees={len(emp)} access_grants={len(log)} terminations={len(term)} "
          f"priv_approvals={len(appr)} reviews={len(reviews)} changes={len(changes)}")
    print("[Phase 2] seeded exceptions by control (answer key only):")
    print(ak.groupby("control_id").size().to_string())


if __name__ == "__main__":
    main()
