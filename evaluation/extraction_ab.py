"""
A/B the table reader: the rows already on disk (old pipeline) against a fresh run (new pipeline).

For a sample of studies that join to the human key, this re-extracts each document with the current
`extract_document` (table type, structure hint, non-outcome filter) and compares both against the
hand-typed numbers in `data/8WR QEX Combined.xlsx`:

- estimate value recall: of the hand-typed estimates for the study, how many appear in our rows
- SE value recall: the same for standard errors
- non-outcome rows: rows whose label is Observations, R2, Constant, Controls, means
- rows and skipped tables

It calls the model, so it costs money. Default is 6 studies.

Usage:
    python evaluation/extraction_ab.py --limit 6
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from evaluation.usage_study import load_content  # noqa: E402
from evaluation.normalisation_audit import to_float  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.extraction.store_estimates import DEFAULT_MODEL  # noqa: E402
from src.extraction.table_estimates import extract_document  # noqa: E402
from src.extraction.table_rules import is_non_outcome_label  # noqa: E402

PROJ = "7efdc60e-e863-480c-929e-616574725e5f"
STUDY_DIR = ROOT / "evaluation" / "results" / "usage_study" / PROJ
OUT = ROOT / "extraction_pipeline" / "outputs"
REPORT = ROOT / "evaluation" / "results" / f"extraction_ab_{date.today().isoformat()}.md"


def human_values() -> dict:
    key = pd.ExcelFile(ROOT / "data" / "8WR QEX Combined.xlsx").parse("Sheet1")
    key.columns = [str(c).replace("\xa0", " ").strip() for c in key.columns]
    out: dict = {}
    for _, row in key.iterrows():
        sid = row.get("StudyID")
        if pd.isna(sid):
            continue
        sid = str(int(sid))
        est = to_float(row.get("Coeff reg"))
        se = to_float(row.get("SE reg"))
        if est is not None:
            out.setdefault(sid, {"estimate": [], "se": []})["estimate"].append(est)
        if se is not None:
            out.setdefault(sid, {"estimate": [], "se": []})["se"].append(se)
    return out


def recall(human: list, ours: list, tol: float = 1e-6) -> tuple:
    found = sum(1 for h in human if any(abs(h - o) < tol for o in ours))
    return found, len(human)


def old_rows(sid: str) -> pd.DataFrame:
    path = OUT / sid / "extracted_data.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()

    human = human_values()
    content_dir = STUDY_DIR / "content"
    names = [p.stem for p in content_dir.glob("*.json")]
    # The human key uses the numeric study id, which is embedded in the document key and the old
    # extraction folder. Map it when exactly one cached document contains the id.
    mapping = {sid: hits[0] for sid in human
               for hits in [[n for n in names if sid in n]] if len(hits) == 1}
    candidates = [sid for sid in sorted(mapping) if (OUT / sid / "extracted_data.csv").exists()][: args.limit]
    print(f"{len(candidates)} studies: {candidates}")

    async def run():
        results = []
        for sid in candidates:
            content = load_content(PROJ, mapping[sid], content_dir)
            new = await extract_document(content, DEFAULT_MODEL, settings.openrouter_api_key)
            results.append((sid, new))
        return results

    new_results = asyncio.run(run())

    agg = Counter()
    lines = ["# Extraction A/B: old rows against the new reader", "",
             "| Study | Est recall old | Est recall new | SE recall old | SE recall new | non-outcome old | non-outcome new | rows old | rows new | skipped | review |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sid, new in new_results:
        old = old_rows(sid)
        h = human.get(sid, {"estimate": [], "se": []})
        old_est = [v for v in (to_float(x) for x in old.get("coefficient", [])) if v is not None]
        new_est = [v for v in (r.get("effect_size") for r in new["estimates"]) if v is not None]
        old_se = [v for v in (to_float(x) for x in old.get("standard_error", [])) if v is not None]
        new_se = [v for v in (r.get("standard_error") for r in new["estimates"]) if v is not None]
        oe, ot = recall(h["estimate"], old_est)
        ne, _ = recall(h["estimate"], new_est)
        os_, ost = recall(h["se"], old_se)
        ns, _ = recall(h["se"], new_se)
        old_non = sum(1 for x in old.get("outcome_name", []) if is_non_outcome_label(str(x)))
        new_non = sum(int(t.get("non_outcome_rows") or 0) for t in new["tables"])
        skipped = sum(1 for t in new["tables"] if t.get("skipped"))
        review = sum(1 for t in new["tables"] if t.get("review"))
        agg.update({"old_est": oe, "new_est": ne, "old_se": os_, "new_se": ns,
                    "old_est_t": ot, "new_est_t": len(h["estimate"]), "old_se_t": ost,
                    "new_se_t": len(h["se"]), "old_non": old_non, "new_non": new_non,
                    "old_rows": len(old), "new_rows": len(new["estimates"]),
                    "skipped": skipped, "review": review})
        lines.append(f"| {sid} | {oe}/{ot} | {ne}/{len(h['estimate'])} | {os_}/{ost} | {ns}/{len(h['se'])} | "
                     f"{old_non} | {new_non} | {len(old)} | {len(new['estimates'])} | {skipped} | {review} |")

    lines += ["", "## Totals", "",
              f"Estimate value recall: old {agg['old_est']}/{agg['old_est_t']} "
              f"({100 * agg['old_est'] / max(1, agg['old_est_t']):.0f}%), "
              f"new {agg['new_est']}/{agg['new_est_t']} ({100 * agg['new_est'] / max(1, agg['new_est_t']):.0f}%).",
              f"SE value recall: old {agg['old_se']}/{agg['old_se_t']} "
              f"({100 * agg['old_se'] / max(1, agg['old_se_t']):.0f}%), "
              f"new {agg['new_se']}/{agg['new_se_t']} ({100 * agg['new_se'] / max(1, agg['new_se_t']):.0f}%).",
              f"Non-outcome rows: old {agg['old_non']}, new {agg['new_non']} (dropped before output).",
              f"Rows: old {agg['old_rows']}, new {agg['new_rows']}. Tables skipped as descriptive: "
              f"{agg['skipped']}. Tables flagged for review: {agg['review']}."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines).encode("ascii", "replace").decode("ascii"))
    print(f"\nwritten to {REPORT}")


if __name__ == "__main__":
    main()
