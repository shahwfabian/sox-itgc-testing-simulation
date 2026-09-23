"""Run the full SOX ITGC testing simulation end to end (Phases 1-5)."""
import runpy
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))

STEPS = [
    "phase1_build_rcm.py",            # Risk and Control Matrix (Excel)
    "phase2_generate_data.py",        # synthetic populations + answer key
    "phase3_test_controls.py",        # pandas control tests (never reads answer key)
    "phase3_sql_tests.py",            # SQL control tests, reconciled to pandas
    "validate_against_answer_key.py", # post-testing recall / precision check
    "phase4_workpapers.py",           # Word workpapers + summary memo
    "phase5_dashboard.py",            # dashboard PNG, site data, Power BI model
]

if __name__ == "__main__":
    for step in STEPS:
        print(f"\n=== {step} ===")
        runpy.run_path(str(SRC / step), run_name="__main__")
    print("\nDone. Open site/index.html via `python -m http.server -d site` or see outputs/.")
