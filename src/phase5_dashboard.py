"""Phase 5 - dashboard outputs.

1. outputs/dashboard/itgc_dashboard.png  - static matplotlib dashboard (README preview)
2. site/data/dashboard.json              - data feed for the interactive web dashboard (site/)
3. outputs/powerbi/*.csv + measures.dax  - star schema to rebuild the dashboard in Power BI
4. site/downloads/                       - RCM, results workbook, workpapers, data for the site
"""
from __future__ import annotations

import json
import shutil
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import common as C
from rcm_definitions import CONTROLS, DOMAINS, RISKS, severity

DOMAIN_COLORS = {"User Access": "#2a78d6", "Privileged Access": "#eb6834", "Change Management": "#1baf7a"}
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
AGE_BUCKETS = [(-1, 90, "0-90 days"), (90, 180, "91-180 days"), (180, 270, "181-270 days"), (270, 10_000, "270+ days")]
SEV_ORDER = ["Critical", "High", "Medium", "Low"]


def age_bucket(d):
    return next(lbl for lo, hi, lbl in AGE_BUCKETS if lo < d <= hi)


def load():
    summary = pd.read_csv(C.OUTPUT_DIR / "test_results_summary.csv")
    allx = pd.read_csv(C.EXCEPTIONS_DIR / "all_exceptions.csv")
    rating = {r["risk_id"]: severity(r)[1] for r in RISKS}
    allx["risk_rating"] = allx.risk_id.map(rating)
    allx["age_bucket"] = allx.exception_age_days.map(age_bucket)
    allx["domain"] = allx.control_id.map({c["control_id"]: c["domain"] for c in CONTROLS})
    return summary, allx


def style_ax(ax, title):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK, pad=10)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def png(summary, allx):
    fig = plt.figure(figsize=(15, 9.2), facecolor="#fcfcfb")
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.1], hspace=0.42, wspace=0.35)
    fig.suptitle(f"SOX ITGC Testing Dashboard - {C.COMPANY}, {C.FISCAL_YEAR}   (SYNTHETIC DATA)",
                 x=0.06, ha="left", fontsize=14, fontweight="bold", color=INK)

    # 1. control effectiveness by domain
    ax = fig.add_subplot(gs[0, 0])
    eff = summary.groupby("domain").conclusion.value_counts().unstack(fill_value=0).reindex(DOMAINS)
    for col in ["Effective", "Exception Noted"]:
        if col not in eff:
            eff[col] = 0
    ax.barh(eff.index, eff["Effective"], color=GOOD, height=0.5, label="Effective", edgecolor="#fcfcfb", linewidth=2)
    ax.barh(eff.index, eff["Exception Noted"], left=eff["Effective"], color=CRITICAL, height=0.5,
            label="Exception noted", edgecolor="#fcfcfb", linewidth=2)
    for i, (e, x) in enumerate(zip(eff["Effective"], eff["Exception Noted"])):
        ax.text(e + x + 0.08, i, f"{e} of {e + x} effective", va="center", fontsize=8, color=INK2)
    ax.invert_yaxis()
    ax.set_xlim(0, eff.sum(axis=1).max() + 2)
    style_ax(ax, "Control effectiveness by domain (count of controls)")
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.1), ncol=2)

    # 2. exceptions by control
    ax = fig.add_subplot(gs[0, 1:])
    s = summary.iloc[::-1]
    ax.barh(s.control_id, s.exceptions, color=[DOMAIN_COLORS[d] for d in s.domain], height=0.6)
    for i, (n, r) in enumerate(zip(s.exceptions, s.exception_rate)):
        ax.text(n + 0.4, i, f"{n}  ({r:.1%})" if n else "0 - effective", va="center", fontsize=8, color=INK2)
    style_ax(ax, "Exceptions by control (count and rate of population)")
    ax.set_xlim(0, s.exceptions.max() * 1.25)
    for d, c in DOMAIN_COLORS.items():
        ax.bar(0, 0, color=c, label=d)
    ax.legend(frameon=False, fontsize=8, loc="lower right")

    # 3. remediation priority heatmap: risk severity x exception age
    ax = fig.add_subplot(gs[1, :2])
    heat = pd.crosstab(allx.risk_rating, allx.age_bucket).reindex(index=SEV_ORDER, columns=[b[2] for b in AGE_BUCKETS],
                                                                  fill_value=0)
    ax.imshow(heat.values, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("b", ["#f0efec", "#256abf"]),
              aspect="auto")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            v = heat.values[i, j]
            ax.text(j, i, str(v) if v else "-", ha="center", va="center", fontsize=11,
                    color="white" if v > heat.values.max() * 0.55 else INK)
    ax.set_xticks(range(heat.shape[1]), heat.columns)
    ax.set_yticks(range(heat.shape[0]), [f"{r} risk" for r in heat.index])
    ax.set_title("Remediation priority: inherent risk severity x exception age (count of exceptions)",
                 loc="left", fontsize=11, fontweight="bold", color=INK, pad=10)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)

    # 4. top priority items
    ax = fig.add_subplot(gs[1, 2])
    ax.axis("off")
    top = allx.sort_values(["priority_score", "exception_age_days"], ascending=False).head(10)
    ax.set_title("Top 10 remediation priorities", loc="left", fontsize=11, fontweight="bold", color=INK, pad=10)
    for i, r in enumerate(top.itertuples()):
        y = 0.95 - i * 0.097
        ax.text(0, y, f"{r.priority_score:.0f}", fontsize=10, fontweight="bold",
                color=CRITICAL if r.priority_tier in ("Critical", "High") else INK2, transform=ax.transAxes)
        ax.text(0.12, y, f"{r.exception_id}  [{r.status}]", fontsize=8, color=INK, transform=ax.transAxes)
        ax.text(0.12, y - 0.04, r.exception_type[:48], fontsize=7, color=MUTED, transform=ax.transAxes)

    C.DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    out = C.DASHBOARD_DIR / "itgc_dashboard.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def site_json(summary, allx):
    rcm = pd.read_excel(C.RCM_DIR / "SOX_ITGC_RCM.xlsx", sheet_name="RCM")
    sqlrec = pd.read_csv(C.OUTPUT_DIR / "sql_vs_pandas_reconciliation.csv")
    akrec = pd.read_csv(C.OUTPUT_DIR / "answer_key_reconciliation.csv")
    heat = pd.crosstab(allx.risk_rating, allx.age_bucket).reindex(index=SEV_ORDER, columns=[b[2] for b in AGE_BUCKETS],
                                                                  fill_value=0)
    counts = {n: len(pd.read_csv(C.DATA_DIR / f"{n}.csv")) for n in
              ["employees", "user_access_log", "termination_log", "privileged_access_approvals", "access_reviews", "change_log"]}
    cols = ["exception_id", "control_id", "domain", "source_record_id", "employee_id", "system_id", "event_date",
            "required_by", "actual_date", "exception_type", "detail", "status", "risk_rating", "exception_age_days",
            "priority_score", "priority_tier"]
    data = {
        "meta": {"company": C.COMPANY, "period": C.FISCAL_YEAR, "as_of": C.TEST_AS_OF.strftime("%Y-%m-%d"),
                 "period_start": C.PERIOD_START.strftime("%Y-%m-%d"), "period_end": C.PERIOD_END.strftime("%Y-%m-%d"),
                 "record_counts": counts},
        "risks": [dict(r, severity_score=severity(r)[0], rating=severity(r)[1]) for r in RISKS],
        "controls": rcm.rename(columns=lambda c: c.lower().replace(" / ", "_").replace(" ", "_")
                               .replace("(", "").replace(")", "")).to_dict("records"),
        "summary": summary.to_dict("records"),
        "heatmap": {"rows": SEV_ORDER, "cols": [b[2] for b in AGE_BUCKETS], "values": heat.values.tolist()},
        "exceptions": allx[cols].sort_values("priority_score", ascending=False).fillna("").to_dict("records"),
        "sql_reconciliation": sqlrec.to_dict("records"),
        "answer_key_reconciliation": akrec.drop(columns=["missed_ids", "unexpected_ids"]).to_dict("records"),
    }
    (C.SITE_DIR / "data").mkdir(parents=True, exist_ok=True)
    (C.SITE_DIR / "data" / "dashboard.json").write_text(json.dumps(data, indent=1, default=str))


def powerbi(summary, allx):
    d = C.OUTPUT_DIR / "powerbi"
    d.mkdir(parents=True, exist_ok=True)
    allx.to_csv(d / "fact_exceptions.csv", index=False)
    summary.to_csv(d / "fact_control_results.csv", index=False)
    pd.DataFrame([dict(r, severity_score=severity(r)[0], rating=severity(r)[1]) for r in RISKS]).to_csv(d / "dim_risk.csv", index=False)
    pd.DataFrame(CONTROLS).to_csv(d / "dim_control.csv", index=False)
    (d / "measures.dax").write_text("""// Power BI measures for the ITGC dashboard (load the CSVs in this folder).
// Relationships: dim_control[control_id] 1-* fact_exceptions[control_id]
//                dim_control[control_id] 1-1 fact_control_results[control_id]
//                dim_risk[risk_id]       1-* dim_control[risk_id]

Exceptions = COUNTROWS ( fact_exceptions )
Open Exceptions = CALCULATE ( [Exceptions], fact_exceptions[status] = "Open" )
Items Tested = SUM ( fact_control_results[population] )
Exception Rate = DIVIDE ( [Exceptions], [Items Tested] )
Controls Tested = DISTINCTCOUNT ( fact_control_results[control_id] )
Effective Controls = CALCULATE ( [Controls Tested], fact_control_results[conclusion] = "Effective" )
Pct Controls Effective = DIVIDE ( [Effective Controls], [Controls Tested] )
Avg Exception Age (days) = AVERAGE ( fact_exceptions[exception_age_days] )
Max Priority Score = MAX ( fact_exceptions[priority_score] )
Critical + High Items = CALCULATE ( [Exceptions], fact_exceptions[priority_tier] IN { "Critical", "High" } )
""")


def downloads():
    dl = C.SITE_DIR / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    shutil.copy(C.RCM_DIR / "SOX_ITGC_RCM.xlsx", dl)
    shutil.copy(C.OUTPUT_DIR / "ITGC_Testing_Results.xlsx", dl)
    shutil.copy(C.DASHBOARD_DIR / "itgc_dashboard.png", dl)
    for name, folder in [("ITGC_Workpapers.zip", C.WORKPAPER_DIR), ("Synthetic_Data.zip", C.DATA_DIR)]:
        with zipfile.ZipFile(dl / name, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(folder.glob("*")):
                z.write(f, f.name)
    for f in C.WORKPAPER_DIR.glob("*.docx"):
        (dl / "workpapers").mkdir(exist_ok=True)
        shutil.copy(f, dl / "workpapers" / f.name)


def main():
    summary, allx = load()
    out = png(summary, allx)
    site_json(summary, allx)
    powerbi(summary, allx)
    downloads()
    print(f"[Phase 5] dashboard image {out.relative_to(C.ROOT)}; site data + downloads refreshed; Power BI model exported")


if __name__ == "__main__":
    main()
