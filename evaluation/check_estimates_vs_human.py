"""
Check extracted estimates against the graduation review's hand extraction (roadmap N6).

The review's quantitative extraction form (20 estimates, 3 studies) gives each
estimate's coefficient and standard error. An estimate counts as found when the
study's extracted estimates contain the same number (within 0.5% or 0.005), and its
standard error is checked on the matching rows.

    python evaluation/check_estimates_vs_human.py --om-qex ../../pipelines/8w-sr/OM_QEX

First result (10 Nov 2026, the review's 2025 machine extraction): 8 of 20 found, 4 of
8 with the right SE; study 121498842 had only a descriptive table extracted.
"""

import argparse
import csv
import glob
import json
import re
from pathlib import Path

FORM = "data/human_extraction/8 week SR QEX Pierre SOF and TEEP(Quant Extraction Form).csv"
COEF, SE, MEAN_DIFF, SE_DIFF = 52, 53, 45, 46  # columns of the extraction form


def num(s):
    s = str(s or "").strip().replace("−", "-")
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def close(a, b):
    return a is not None and b is not None and abs(a - b) <= max(0.0051, abs(b) * 0.005)


def human_estimates(om: Path):
    rows = list(csv.reader(open(om / FORM, encoding="cp1252", errors="replace")))
    for r in rows[4:]:
        if len(r) > SE and r[2].strip():
            coef = num(r[COEF]) if r[COEF].strip() else num(r[MEAN_DIFF])
            se = num(r[SE]) if r[SE].strip() else num(r[SE_DIFF])
            yield {"study": r[2].strip(), "outcome": r[22], "coef": coef, "se": se}


def check(human, machine_by_study):
    found = se_ok = se_total = 0
    missing = []
    for h in human:
        outs = machine_by_study.get(h["study"], [])
        hits = [o for o in outs if close(num(o.get("effect_size")), h["coef"])]
        if not hits:
            missing.append((h["study"], h["outcome"][:50], h["coef"], len(outs)))
            continue
        found += 1
        if h["se"] is not None:
            se_total += 1
            se_ok += any(close(num(o.get("standard_error")), h["se"]) for o in hits)
    return found, se_ok, se_total, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--om-qex", required=True)
    args = ap.parse_args()
    om = Path(args.om_qex)
    paper_of = {r["Key"]: r["paper_id"] for r in csv.DictReader(
        open(om / "data/final_114_combined/fulltext_metadata_114.csv", encoding="cp1252", errors="replace"))}
    machine = {}
    for f in glob.glob(str(om / "outputs/phase3/*_phase3.json")):
        machine[paper_of.get(Path(f).name.split("_")[0])] = json.load(open(f, encoding="utf-8")).get("outcomes", [])
    human = list(human_estimates(om))
    found, se_ok, se_total, missing = check(human, machine)
    print(f"hand-extracted {len(human)} | found {found} | SE right {se_ok}/{se_total}")
    for m in missing:
        print("  missing:", m)


if __name__ == "__main__":
    main()
