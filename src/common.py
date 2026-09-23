"""Shared configuration for the SOX ITGC Testing Simulation.

Every parameter a tester would pull from the company's IT policy (SLAs, the audit
period, the business-day calendar, which access levels count as privileged) lives
here, so the generator, the pandas tests and the SQL tests all read one source.

ALL DATA IN THIS PROJECT IS SYNTHETIC. "Meridian Financial Group" is fictional.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"                 # populations the tester samples from
ANSWER_KEY_DIR = ROOT / "answer_key"     # seeded exceptions: NOT read by Phase 3 tests
OUTPUT_DIR = ROOT / "outputs"
RCM_DIR = OUTPUT_DIR / "rcm"
EXCEPTIONS_DIR = OUTPUT_DIR / "exceptions"
WORKPAPER_DIR = OUTPUT_DIR / "workpapers"
DASHBOARD_DIR = OUTPUT_DIR / "dashboard"
SQL_DIR = ROOT / "sql"
SITE_DIR = ROOT / "site"

COMPANY = "Meridian Financial Group (fictional)"
FISCAL_YEAR = "FY2025"
PERIOD_START = pd.Timestamp("2025-01-01")
PERIOD_END = pd.Timestamp("2025-12-31")
# Fieldwork "as-of" date: open exceptions are aged to this date.
TEST_AS_OF = pd.Timestamp("2026-01-30")
RANDOM_SEED = 20250101

# --- Policy parameters (the thresholds each control is tested against) -------
TERMINATION_REVOCATION_SLA_BD = 5   # ITGC-UA-02: revoke all access within 5 business days
HR_NOTIFICATION_SLA_BD = 1          # ITGC-UA-03: HR notifies IT within 1 business day
EMERGENCY_RETRO_APPROVAL_BD = 2     # ITGC-CM-01: emergency changes approved within 2 BD after
ACCESS_REVIEW_DUE_DAYS = 30         # ITGC-UA-04: quarterly review due 30 days after quarter end

PRIVILEGED_ACCESS_LEVELS = ["Administrator", "Superuser", "Database Administrator"]
STANDARD_ACCESS_LEVELS = ["Read Only", "Standard User", "Power User"]

SYSTEMS = {
    "GL01": "Core General Ledger",
    "LSP": "Loan Servicing Platform",
    "TMS": "Treasury Management System",
    "FCR": "Financial Close & Consolidation",
}

# US market holidays (NYSE calendar) covering the period and fieldwork window.
HOLIDAYS = pd.to_datetime([
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
    "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16",
])
_HOLIDAY_ARR = HOLIDAYS.values.astype("datetime64[D]")


def business_days_elapsed(start, end) -> np.ndarray:
    """Business days after `start` up to and including `end`.

    Friday termination -> Monday revocation = 1 business day. Works element-wise
    on Series; NaT inputs return NaN.
    """
    s = pd.to_datetime(pd.Series(start)).dt.normalize()
    e = pd.to_datetime(pd.Series(end)).dt.normalize()
    out = np.full(len(s), np.nan)
    ok = (s.notna() & e.notna()).to_numpy()
    if ok.any():
        sd = s[ok].values.astype("datetime64[D]") + np.timedelta64(1, "D")
        ed = e[ok].values.astype("datetime64[D]") + np.timedelta64(1, "D")
        out[ok] = np.busday_count(sd, ed, holidays=_HOLIDAY_ARR)
    return out


def add_business_days(dates, n: int) -> pd.Series:
    """The n-th business day after each date (the SLA deadline).

    A Saturday event with n=2 gives Tuesday (Mon = 1st, Tue = 2nd), matching the
    SQL calendar logic in sql/*.sql.
    """
    d = pd.to_datetime(pd.Series(dates)).dt.normalize().values.astype("datetime64[D]")
    return pd.Series(pd.to_datetime(np.busday_offset(d, n, roll="backward", holidays=_HOLIDAY_ARR)))


def is_business_day(d: pd.Timestamp) -> bool:
    return bool(np.is_busday(np.datetime64(d.date()), holidays=_HOLIDAY_ARR))
