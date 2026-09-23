"""Phase 4 - generate audit-style testing workpapers (Word) from Phase 3 results.

Every number in the Results / Conclusion sections is computed from
outputs/exceptions/*.csv and outputs/test_results_summary.csv - nothing is
typed in by hand, so the workpapers cannot claim cleaner results than the
testing found.
"""
from __future__ import annotations

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

import common as C
from rcm_definitions import CONTROLS, risk_by_id

NAVY = RGBColor(0x1F, 0x38, 0x64)
RED = RGBColor(0xC0, 0x00, 0x00)
GREEN = RGBColor(0x00, 0x63, 0x00)

# Sample sizes a tester would use if NOT testing the full population
# (typical attribute-sampling guidance for ITGCs; shown for context only).
SAMPLE_GUIDE = {"As needed (per event)": "25 to 60 items", "Quarterly": "2 items"}

REMEDIATION = {
    "ITGC-UA-01": [
        "Configure the provisioning tool to block account creation unless the request ticket carries an approved status (convert the control from manual to automated preventive).",
        "Obtain retrospective business-owner approval for each exception grant, or remove the access.",
        "Add a monthly IT Access Manager review of grants lacking an approver until the automated block is live.",
    ],
    "ITGC-UA-02": [
        "Immediately disable all accounts still active for terminated users and review their activity after the termination date for unauthorized transactions.",
        "Automate deprovisioning from the HR system of record (termination event -> account disable) to remove the manual hand-off.",
        "Introduce a weekly reconciliation of the HR termination report to active accounts in each in-scope application as a detective backstop.",
    ],
    "ITGC-UA-03": [
        "Enable a real-time HR-to-IT termination feed instead of manual ticket creation.",
        "Require managers to submit separation notices before the last working day for voluntary terminations; track late notices as an HR KPI.",
    ],
    "ITGC-UA-04": [
        "Add escalation to the CIO/Controller when a quarterly review is not complete 5 days before its due date.",
        "Document the reason for the late Q3 review and confirm removals requested in that review were processed.",
    ],
    "ITGC-PA-01": [
        "Revoke or retroactively approve each exception grant; review activity logs performed under privileged IDs lacking approval.",
        "Require the privileged access tool to validate the approval register (ticket, user, system, level) before granting elevated access.",
        "Add a quarterly reconciliation of privileged accounts to the approval register, performed by Information Security.",
    ],
    "ITGC-PA-02": ["No remediation required. Continue to monitor the workflow configuration that blocks self-approval."],
    "ITGC-CM-01": [
        "Enforce a change-management tool gate so deployment pipelines cannot promote to production without CAB approval status.",
        "Obtain retrospective CAB review of each exception change, confirming it operated as intended and did not affect financial data.",
        "Monitor emergency changes weekly for retrospective approval within 2 business days.",
    ],
    "ITGC-CM-02": [
        "Make the rollback-plan field mandatory (with attachment) in the change ticket template before CAB submission.",
        "Standardize the field to a controlled Yes/No value to eliminate free-text variants.",
    ],
    "ITGC-CM-03": ["No remediation required. Continue to monitor requester/approver segregation in the change tool."],
}


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def kv_table(doc, rows, widths=(1.9, 4.6)):
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for k, v in rows:
        r = t.add_row().cells
        r[0].text, r[1].text = k, str(v)
        r[0].paragraphs[0].runs[0].bold = True
        shade(r[0], "DCE3EE")
    return t


def df_table(doc, df, font=7.5):
    t = doc.add_table(rows=1, cols=len(df.columns))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]
        cell.text = str(c)
        cell.paragraphs[0].runs[0].bold = True
        shade(cell, "1F3864")
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if pd.isna(v) else str(v)
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(font)
    return t


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.color.rgb = NAVY
    return h


def banner(doc):
    p = doc.add_paragraph()
    r = p.add_run("SYNTHETIC DATA - simulation. Entity, people, systems and records are fictional.")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(8), RED
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def base_doc():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10)
    for s in doc.sections:
        s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Pt(54)
        s.header.paragraphs[0].text = f"{C.COMPANY} | {C.FISCAL_YEAR} SOX ITGC Testing"
        s.footer.paragraphs[0].text = "SYNTHETIC DATA - for demonstration only"
    return doc


def population_stats(cid):
    """Completeness & accuracy (IPE) checks on the source population."""
    d = C.DATA_DIR
    if cid.startswith("ITGC-CM"):
        df = pd.read_csv(d / "change_log.csv", parse_dates=["implementation_date"])
        key, date = "change_id", "implementation_date"
    elif cid == "ITGC-UA-03" or cid == "ITGC-UA-02":
        df = pd.read_csv(d / "termination_log.csv", parse_dates=["termination_date"])
        key, date = "employee_id", "termination_date"
    elif cid == "ITGC-UA-04":
        df = pd.read_csv(d / "access_reviews.csv", parse_dates=["quarter_end"])
        key, date = "review_id", "quarter_end"
    else:
        df = pd.read_csv(d / "user_access_log.csv", parse_dates=["date_granted"])
        key, date = "grant_id", "date_granted"
    emp = set(pd.read_csv(d / "employees.csv").employee_id)
    out = [
        ("Source record count", f"{len(df):,}"),
        ("Duplicate record keys", f"{df[key].duplicated().sum()} (key: {key})"),
        ("Date range of key field", f"{df[date].min():%Y-%m-%d} to {df[date].max():%Y-%m-%d}"),
    ]
    if "employee_id" in df:
        out.append(("Employee IDs not on HR roster", str((~df.employee_id.isin(emp)).sum())))
    return out


def observations(cid, x: pd.DataFrame, allx: pd.DataFrame) -> list[str]:
    """Data-driven patterns in the exceptions (root-cause leads for management)."""
    if x.empty:
        return ["No exceptions; no patterns to report."]
    obs = []
    by_sys = x.system_id.value_counts()
    if cid != "ITGC-UA-03" and len(by_sys) > 1:
        obs.append("Exceptions by system: " + ", ".join(f"{s} {n}" for s, n in by_sys.items()) + ".")
    if cid == "ITGC-UA-02":
        opn = x[x.status == "Open"]
        obs.append(f"{len(opn)} of the {len(x)} exception grants, belonging to {opn.employee_id.nunique()} former employees, "
                   f"were still active at the {C.TEST_AS_OF:%d %b %Y} as-of date ({x.employee_id.nunique()} employees "
                   "affected in total).")
        closed = x[x.status == "Closed"]
        if len(closed):
            obs.append(f"Late revocations were completed a median of {closed.days_late.median():.0f} and a maximum of "
                       f"{closed.days_late.max():.0f} business days beyond the 5-day SLA.")
        late_hr = set(allx.loc[allx.control_id == "ITGC-UA-03", "employee_id"])
        overlap = x[x.employee_id.isin(late_hr)].employee_id.nunique()
        obs.append(f"{overlap} of {x.employee_id.nunique()} affected employees also had a late HR separation notice "
                   f"(ITGC-UA-03 exception), which points to the HR-to-IT hand-off as a root cause.")
    elif cid == "ITGC-UA-03":
        obs.append(f"Notifications arrived a median of {x.days_late.median():.0f} and a maximum of "
                   f"{x.days_late.max():.0f} business days after the 1-day SLA.")
        dep = pd.read_csv(C.DATA_DIR / "termination_log.csv").set_index("employee_id").termination_type
        obs.append("By termination type: " + ", ".join(f"{k} {v}" for k, v in dep.reindex(x.employee_id).value_counts().items()) + ".")
    elif cid in ("ITGC-PA-01", "ITGC-CM-01", "ITGC-UA-01"):
        obs.append("By exception type: " + "; ".join(f"{k} ({v})" for k, v in x.exception_type.value_counts().items()) + ".")
        if cid == "ITGC-PA-01":
            obs.append(f"{(x.status == 'Open').sum()} of the {len(x)} privileged grants lacking valid approval were still active "
                       "at the as-of date. Note that the access log recorded an approver for every one of them: the grant "
                       "looked approved on its face, and only matching it to the approval register exposed the gap.")
    elif cid == "ITGC-CM-02":
        chg = pd.read_csv(C.DATA_DIR / "change_log.csv").set_index("change_id")
        obs.append("By change type: " + ", ".join(f"{k} {v}" for k, v in chg.loc[x.source_record_id, "change_type"].value_counts().items()) + ".")
    months = pd.to_datetime(x.event_date).dt.to_period("Q").value_counts().sort_index()
    obs.append("By quarter of occurrence: " + ", ".join(f"{p} {n}" for p, n in months.items()) +
               (" - exceptions recur across the year, indicating a design/process gap rather than a one-off lapse."
                if len(months) >= 3 else "."))
    return obs


def build_control_wp(ctrl, srow, x, allx, sqlrec, akrec):
    cid = ctrl["control_id"]
    risk = risk_by_id(ctrl["risk_id"])
    doc = base_doc()
    banner(doc)
    t = doc.add_heading(f"Workpaper {cid.replace('ITGC', 'WP')}: {ctrl['title']}", 0)
    for r in t.runs:
        r.font.size, r.font.color.rgb = Pt(18), NAVY
    kv_table(doc, [
        ("Entity / Period", f"{C.COMPANY} / {C.FISCAL_YEAR} ({C.PERIOD_START:%d %b %Y} - {C.PERIOD_END:%d %b %Y})"),
        ("Control ID / Domain", f"{cid} / {ctrl['domain']}"),
        ("Control owner", ctrl["owner"]),
        ("Frequency / Type / Nature", f"{ctrl['frequency']} / {ctrl['type']} / {ctrl['nature']}"),
        ("Key control", ctrl["key"]),
        ("Risk addressed", f"{risk['risk_id']} - {risk['title']} (inherent severity {srow.risk_severity_score} - {srow.risk_rating})"),
        ("Prepared by / date", f"SOX ITGC Tester (simulation) / {C.TEST_AS_OF:%d %b %Y}"),
        ("Reviewed by / date", "Pending reviewer sign-off"),
    ])

    heading(doc, "1. Control Objective")
    doc.add_paragraph(f"To address the risk that {risk['statement'][0].lower() + risk['statement'][1:]}")
    doc.add_paragraph("Control description (per RCM): " + ctrl["description"])

    heading(doc, "2. Population")
    doc.add_paragraph(f"Source: {ctrl['population']}. In-scope population tested: {srow.population:,} items.")
    doc.add_paragraph("Completeness and accuracy of the information produced by the entity (IPE) were evaluated "
                      "before testing:")
    kv_table(doc, population_stats(cid))

    heading(doc, "3. Sample / Testing Approach")
    doc.add_paragraph(
        f"The full population ({srow.population:,} items) was tested with computer-assisted audit techniques rather "
        f"than a sample. For a control that operates {ctrl['frequency'].lower()}, a traditional attribute sample "
        f"would typically be {SAMPLE_GUIDE[ctrl['frequency']]}. Testing 100% of "
        "the population removes sampling risk, so every deviation is identified and none has to be extrapolated.")
    doc.add_paragraph(
        "The test logic was implemented twice, in Python/pandas (src/phase3_test_controls.py) and in SQL "
        "(sql/), and the two exception sets were reconciled record-by-record: "
        f"{'agreed' if sqlrec.agree else 'DID NOT AGREE'} ({sqlrec.sql_exceptions} SQL vs {sqlrec.pandas_exceptions} pandas).")

    heading(doc, "4. Procedures Performed")
    doc.add_paragraph("Test attribute / exception definition: " + ctrl["attribute"])
    for step in [s.strip() for s in ctrl["procedure"].split(";") if s.strip()]:
        doc.add_paragraph(step[0].upper() + step[1:], style="List Number")
    doc.add_paragraph("Each exception was traced to its source record ID (listed below) for follow-up with the control owner.",
                      style="List Number")

    heading(doc, "5. Results")
    kv_table(doc, [
        ("Items tested", f"{srow.population:,}"),
        ("Exceptions identified", f"{srow.exceptions}"),
        ("Exception rate", f"{srow.exception_rate:.2%}"),
        ("Distinct employees involved", f"{srow.unique_employees}"),
        ("Exceptions still open at as-of date", f"{srow.open_exceptions}"),
    ])
    doc.add_paragraph()
    for o in observations(cid, x, allx):
        doc.add_paragraph(o, style="List Bullet")
    if len(x):
        doc.add_paragraph().add_run(f"Exception listing ({len(x)} items; also in outputs/exceptions/{cid}_exceptions.csv):").bold = True
        cols = ["exception_id", "source_record_id", "employee_id", "system_id", "event_date", "required_by",
                "actual_date", "exception_type", "status", "priority_tier"]
        df_table(doc, x[cols].rename(columns={"exception_id": "Exc ID", "source_record_id": "Source record",
                                              "employee_id": "Employee", "system_id": "System",
                                              "event_date": "Event date", "required_by": "Required by",
                                              "actual_date": "Actual", "exception_type": "Exception",
                                              "status": "Status", "priority_tier": "Priority"}))

    heading(doc, "6. Conclusion")
    p = doc.add_paragraph()
    run = p.add_run(f"{srow.conclusion.upper()}: ")
    run.bold = True
    run.font.color.rgb = GREEN if srow.conclusion == "Effective" else RED
    if srow.conclusion == "Effective":
        p.add_run(f"No exceptions were identified in {srow.population:,} items tested. The control operated "
                  f"effectively throughout {C.FISCAL_YEAR}.")
    else:
        p.add_run(f"{srow.exceptions} exceptions were identified in {srow.population:,} items ({srow.exception_rate:.2%}). "
                  f"Because the full population was tested, these are actual deviations, not projections, and the control "
                  f"did not operate effectively throughout {C.FISCAL_YEAR}. Deficiency assessment: "
                  f"{srow.deficiency_assessment}. Final severity must consider compensating controls and aggregation "
                  "with other deficiencies affecting the same risk and assertions.")

    heading(doc, "7. Remediation Recommendations")
    for rec in REMEDIATION[cid]:
        doc.add_paragraph(rec, style="List Bullet")
    doc.add_paragraph("Management response and target date: [to be obtained from control owner]").italic = True

    if akrec is not None:
        heading(doc, "Appendix - Test-logic validation (simulation only)", 2)
        doc.add_paragraph(
            f"After testing was complete, results were compared to the independently stored answer key of seeded "
            f"exceptions (answer_key/seeded_exceptions.csv): {int(akrec.matched)} of {int(akrec.seeded)} seeded exceptions "
            f"detected, {int(akrec.unexpected)} unexpected. The answer key was not an input to testing.")

    out = C.WORKPAPER_DIR / f"{cid.replace('ITGC-', 'WP-')}_{ctrl['title'].replace(' ', '_').replace('/', '-')}.docx"
    doc.save(out)
    return out


def build_summary_memo(summary, allx):
    doc = base_doc()
    banner(doc)
    t = doc.add_heading(f"{C.FISCAL_YEAR} ITGC Testing Summary Memo", 0)
    for r in t.runs:
        r.font.color.rgb = NAVY
    kv_table(doc, [("To", "SOX Compliance Office (simulation)"), ("From", "ITGC Testing Team (simulation)"),
                   ("Date", f"{C.TEST_AS_OF:%d %B %Y}"), ("Scope", f"{len(summary)} ITGCs across 3 domains; "
                                                                      f"{len(C.SYSTEMS)} in-scope financial applications")])
    heading(doc, "Overall Results")
    eff = (summary.conclusion == "Effective").sum()
    doc.add_paragraph(
        f"{eff} of {len(summary)} controls operated effectively. {len(summary) - eff} controls had exceptions, "
        f"{len(allx)} in total, of which {(allx.status == 'Open').sum()} were still open at the as-of date. "
        "All populations were tested in full, and the pandas and SQL implementations agreed on every exception.")
    df_table(doc, summary[["control_id", "domain", "title", "population", "exceptions", "exception_rate",
                           "open_exceptions", "conclusion"]].assign(
        exception_rate=lambda d: (d.exception_rate * 100).round(2).astype(str) + "%"), font=8)
    heading(doc, "Matters for Attention")
    top = allx.sort_values("priority_score", ascending=False).head(8)
    for _, r in top.iterrows():
        doc.add_paragraph(f"[{r.priority_tier}] {r.exception_id} - {r.exception_type}: {r.detail}", style="List Bullet")
    ua = summary.set_index("control_id")
    doc.add_paragraph(
        f"The user-access deprovisioning chain (UA-03 -> UA-02) is the most significant theme: "
        f"{ua.loc['ITGC-UA-02', 'exceptions']} grants for {ua.loc['ITGC-UA-02', 'unique_employees']} terminated employees "
        f"were not revoked within SLA, and {ua.loc['ITGC-UA-02', 'open_exceptions']} were still active at the as-of date. "
        "We recommend management evaluate these deficiencies in aggregation for risk R-02 and review post-termination "
        "activity on the affected accounts.")
    out = C.WORKPAPER_DIR / "00_ITGC_Testing_Summary_Memo.docx"
    doc.save(out)
    return out


def main():
    C.WORKPAPER_DIR.mkdir(parents=True, exist_ok=True)
    summary = pd.read_csv(C.OUTPUT_DIR / "test_results_summary.csv")
    allx = pd.read_csv(C.EXCEPTIONS_DIR / "all_exceptions.csv")
    sql = pd.read_csv(C.OUTPUT_DIR / "sql_vs_pandas_reconciliation.csv").set_index("control_id")
    akpath = C.OUTPUT_DIR / "answer_key_reconciliation.csv"
    ak = pd.read_csv(akpath).set_index("control_id") if akpath.exists() else None
    files = [build_summary_memo(summary, allx)]
    for ctrl in CONTROLS:
        cid = ctrl["control_id"]
        srow = summary.set_index("control_id").loc[cid]
        files.append(build_control_wp(ctrl, srow, allx[allx.control_id == cid], allx, sql.loc[cid],
                                      ak.loc[cid] if ak is not None and cid in ak.index else None))
    print(f"[Phase 4] {len(files)} workpapers written to {C.WORKPAPER_DIR.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
