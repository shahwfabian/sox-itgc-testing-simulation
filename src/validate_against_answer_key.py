"""Reconcile Phase 3 findings to the Phase 2 answer key (run AFTER testing).

This is the only script that reads answer_key/. It measures whether the testing
logic found every seeded exception (recall) and nothing spurious (precision).
"""
import pandas as pd

import common as C
from rcm_definitions import CONTROLS


def main():
    found = pd.read_csv(C.EXCEPTIONS_DIR / "all_exceptions.csv", dtype=str)
    key = pd.read_csv(C.ANSWER_KEY_DIR / "seeded_exceptions.csv", dtype=str)
    # UA-03 / UA-04 key on employee / review id; everything else on the source record id
    f = set(zip(found.control_id, found.source_record_id))
    k = set(zip(key.control_id, key.record_key))
    rows = []
    for cid in [c["control_id"] for c in CONTROLS]:
        fk = {r for c, r in f if c == cid}
        kk = {r for c, r in k if c == cid}
        tp = len(fk & kk)
        rows.append(dict(control_id=cid, seeded=len(kk), detected=len(fk), matched=tp,
                         missed=len(kk - fk), unexpected=len(fk - kk),
                         recall=round(tp / len(kk), 3) if kk else 1.0,
                         precision=round(tp / len(fk), 3) if fk else 1.0,
                         missed_ids=", ".join(sorted(kk - fk)), unexpected_ids=", ".join(sorted(fk - kk))))
    rec = pd.DataFrame(rows)
    rec.to_csv(C.OUTPUT_DIR / "answer_key_reconciliation.csv", index=False)
    print("[Validate] Phase 3 results vs seeded answer key")
    print(rec.drop(columns=["missed_ids", "unexpected_ids"]).to_string(index=False))
    bad = rec[(rec.missed > 0) | (rec.unexpected > 0)]
    if len(bad):
        print("\nDifferences:\n" + bad[["control_id", "missed_ids", "unexpected_ids"]].to_string(index=False))
    else:
        print("\nAll seeded exceptions detected; no false positives.")


if __name__ == "__main__":
    main()
