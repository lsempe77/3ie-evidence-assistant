"""
One-off (11 Nov 2026): study facts extracted before this date stored pages counting from 0.
Add 1 to every page in records without "page_base": 1, and mark them, so a rerun changes nothing.

    python scripts/fix_fact_pages.py --project-id <uuid>
"""

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

LISTS = ("cost_per_beneficiary", "transfer_value", "benefit_cost", "headline_effects")


def shifted(facts: dict) -> dict:
    out = dict(facts)
    for key in LISTS:
        out[key] = [{**x, "page": x["page"] + 1} if isinstance(x.get("page"), int) else x for x in facts.get(key) or []]
    out["page_base"] = 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    args = ap.parse_args()
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(base_url=url, headers=h, timeout=120) as db:
        rows = db.get("/study_facts", params={"select": "id,rag_project_id,doc_key,facts",
                                              "rag_project_id": f"eq.{args.project_id}", "limit": "10000"}).json()
        todo = [r for r in rows if r["facts"].get("page_base") != 1]
        updates = [{**r, "facts": shifted(r["facts"])} for r in todo]
        for i in range(0, len(updates), 100):
            db.post("/study_facts", params={"on_conflict": "id"}, json=updates[i:i + 100],
                    headers={"Prefer": "return=minimal,resolution=merge-duplicates"}).raise_for_status()
    print(f"{len(updates)} of {len(rows)} records shifted to pages counting from 1")


if __name__ == "__main__":
    sys.exit(main())
