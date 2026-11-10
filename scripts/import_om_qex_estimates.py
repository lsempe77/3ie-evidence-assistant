"""
Import the 8-week graduation review's extracted estimates into effect_estimates
(roadmap N6 step 1). No model calls: it reads the review's saved extraction.

    python scripts/import_om_qex_estimates.py --project-id <uuid> \
        --om-qex "../../pipelines/8w-sr/OM_QEX" [--replace]

Joins: OM_QEX Zotero key -> EPPI paper_id (data/final_114_combined/fulltext_metadata_114.csv)
-> collection documents (evaluation/benchmark/graduation_included_studies.csv).
Estimates of a study held as several documents are attached to its first document.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "om_qex_2025"
BATCH = 500


def as_float(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("−", "-")
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)  # thousands separators: 4,408 -> 4408
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def as_int(v):
    f = as_float(v)
    return int(f) if f is not None and f.is_integer() and abs(f) < 2**31 else None


def page_of(position: str):
    m = re.search(r"\bpage\s*(\d+)", position or "", re.I)
    return int(m.group(1)) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--om-qex", required=True)
    ap.add_argument("--replace", action="store_true", help="delete this source's rows for the project first")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    om = Path(args.om_qex)
    paper_of = {r["Key"]: r["paper_id"] for r in csv.DictReader(
        open(om / "data/final_114_combined/fulltext_metadata_114.csv", encoding="cp1252", errors="replace"))}
    docs_of = {r["eppi_id"]: [d for d in r["doc_ids"].split("|") if d]
               for r in csv.DictReader(open(ROOT / "evaluation/benchmark/graduation_included_studies.csv", encoding="utf-8"))
               if r["in_collection"] == "yes"}

    with httpx.Client(base_url=url, headers=headers, timeout=60) as client:
        documents = client.get("/documents", params={"select": "id,filename", "rag_project_id": f"eq.{args.project_id}"}).json()
        doc_uuid = {d["filename"]: d["id"] for d in documents}

        rows, studies, skipped = [], 0, 0
        for f in sorted(glob.glob(str(om / "outputs/phase3/*_phase3.json"))):
            zkey = Path(f).name.split("_")[0]
            eppi = paper_of.get(zkey)
            doc_ids = docs_of.get(eppi or "")
            if not doc_ids:
                skipped += 1
                continue
            doc_key = doc_ids[0]
            studies += 1
            for o in json.load(open(f, encoding="utf-8")).get("outcomes", []):
                if not o.get("outcome_name"):
                    continue
                p = o.get("p_value")
                rows.append({
                    "rag_project_id": args.project_id, "document_id": doc_uuid.get(doc_key), "doc_key": doc_key,
                    "source": SOURCE, "study_ref": eppi, "table_number": str(o.get("table_number") or "") or None,
                    "outcome_name": str(o["outcome_name"])[:500], "outcome_description": o.get("outcome_description"),
                    "treatment_arm": o.get("treatment_arm"), "subgroup": o.get("subgroup"),
                    "effect_size": as_float(o.get("effect_size")), "standard_error": as_float(o.get("standard_error")),
                    "p_value": as_float(p), "p_text": None if as_float(p) is not None or p is None else str(p),
                    "ci_text": None if o.get("confidence_interval") is None else str(o.get("confidence_interval")),
                    "sample_size": as_int(o.get("sample_size")), "literal_text": o.get("literal_text"),
                    "text_position": o.get("text_position"), "page": page_of(o.get("text_position") or ""),
                    "extraction_method": o.get("_extraction_method"),
                })

        if args.replace:
            client.delete("/effect_estimates", params={"rag_project_id": f"eq.{args.project_id}", "source": f"eq.{SOURCE}"}).raise_for_status()
        for i in range(0, len(rows), BATCH):
            r = client.post("/effect_estimates", json=rows[i:i + BATCH], headers={"Prefer": "return=minimal"})
            if r.status_code >= 400:
                sys.exit(f"insert failed: {r.status_code} {r.text[:300]}")
    print(f"{len(rows)} estimates from {studies} studies imported ({skipped} studies not in the collection)")


if __name__ == "__main__":
    main()
