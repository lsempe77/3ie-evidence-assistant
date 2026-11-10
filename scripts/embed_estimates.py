"""
Embed the outcome text of extracted estimates that have no embedding yet (roadmap N6),
so a question can find each study's closest estimates (estimates_for_studies).

    python scripts/embed_estimates.py --project-id <uuid> [--source tables_v1]

Text embedded per estimate: outcome, treatment arm and subgroup. Cohere embed-v4.0,
about 20 tokens per estimate.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.retrieval.study_cards import embed_documents  # noqa: E402

PAGE = 500
BATCH = 50


def estimate_text(r: dict) -> str:
    parts = [r["outcome_name"]]
    if r.get("treatment_arm"):
        parts.append(f"arm: {r['treatment_arm']}")
    if r.get("subgroup"):
        parts.append(f"subgroup: {r['subgroup']}")
    return " | ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--source", default="tables_v1")
    args = ap.parse_args()
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    done = 0
    with httpx.Client(base_url=url, headers=headers, timeout=120) as db:
        while True:
            rows = db.get("/effect_estimates", params={
                "select": "id,rag_project_id,doc_key,source,outcome_name,treatment_arm,subgroup",
                "rag_project_id": f"eq.{args.project_id}", "source": f"eq.{args.source}",
                "embedding": "is.null", "limit": str(PAGE)}).json()
            if not rows:
                break
            vectors = embed_documents([estimate_text(r) for r in rows])
            payload = [{**r, "embedding": [float(x) for x in v]} for r, v in zip(rows, vectors)]
            for i in range(0, len(payload), BATCH):
                resp = None
                for attempt in range(5):  # the small Supabase instance times out under large vector writes
                    try:
                        resp = db.post("/effect_estimates", params={"on_conflict": "id"}, json=payload[i:i + BATCH],
                                       headers={"Prefer": "return=minimal,resolution=merge-duplicates"})
                        if resp.status_code < 500:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(5 * (attempt + 1))
                if resp is None:
                    raise RuntimeError("Supabase did not answer after 5 attempts")
                resp.raise_for_status()
            done += len(rows)
            print(f"  embedded {done}", flush=True)
    print(f"{done} estimates embedded")


if __name__ == "__main__":
    main()
