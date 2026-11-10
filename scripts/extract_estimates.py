"""
Extract effect estimates from every processed document of a project into
effect_estimates (roadmap N6 step 2), from the Docling output saved in R2.

    python scripts/extract_estimates.py --project-id <uuid> [--model anthropic/claude-haiku-5.5] [--only <doc_key>]

Only rows whose cells were found verbatim in the table are stored. Rows of this
source for a document are replaced on each run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.extraction.table_estimates import extract_document  # noqa: E402

SOURCE = "tables_v1"
DOC_CONCURRENCY = 4


def r2():
    import boto3

    return boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])


def _finite(x):
    return x if isinstance(x, (int, float)) and math.isfinite(x) else None


def _clean(v):
    return v.replace("\x00", "") if isinstance(v, str) else v


def rows_for(project_id, doc, out, model):
    rows = []
    for e in out["estimates"]:
        if not e["grounded"] or _finite(e["effect_size"]) is None:
            continue
        ci = f"[{e['ci_low']}, {e['ci_high']}]" if e["ci_low"] is not None else None
        rows.append({
            "rag_project_id": project_id, "document_id": doc["id"], "doc_key": doc["filename"], "source": SOURCE,
            "table_number": e["table_label"][:120], "outcome_name": (e["outcome"] or e["row_label"] or "?")[:500],
            "treatment_arm": e["arm"] or None, "subgroup": e["subgroup"] or None,
            "effect_size": e["effect_size"], "standard_error": _finite(e["standard_error"]),
            "p_value": p if (p := _finite(e["p_value"])) is not None and 0 <= p <= 1 else None,
            "p_text": ("*" * e["stars"]) if e["stars"] else None, "ci_text": ci, "sample_size": n if (n := _finite(e["sample_size"])) is not None and abs(n) < 2**31 and n == int(n) else None,
            "literal_text": (e["estimate_cell"] + (" " + e["se_cell"] if e["se_cell"] else ""))[:500],
            "text_position": f"{e['table_label']}, row '{e['row_label']}', column '{e['column_label']}'"[:500],
            "page": e["page"], "extraction_method": model,
        })
    for r in rows:
        if r["sample_size"] is not None:
            r["sample_size"] = int(r["sample_size"])
        for k, v in r.items():
            r[k] = _clean(v)
    return rows


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--model", default="anthropic/claude-haiku-5.5")
    ap.add_argument("--only")
    ap.add_argument("--skip-done", action="store_true", help="skip documents that already have rows of this source")
    args = ap.parse_args()
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    bucket, s3 = os.environ["R2_BUCKET_NAME"], r2()

    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=120) as db:
        params = {"select": "id,filename", "rag_project_id": f"eq.{args.project_id}", "status": "eq.completed"}
        if args.only:
            params["filename"] = f"eq.{args.only}"
        docs = (await db.get("/documents", params=params)).json()
        if args.skip_done:
            have = (await db.get("/effect_estimates", params={"select": "doc_key", "rag_project_id": f"eq.{args.project_id}",
                                                              "source": f"eq.{SOURCE}", "limit": "100000"})).json()
            done_keys = {h["doc_key"] for h in have}
            docs = [d for d in docs if d["filename"] not in done_keys]
        print(f"{len(docs)} documents", flush=True)
        sem = asyncio.Semaphore(DOC_CONCURRENCY)
        totals = {"docs": 0, "estimates": 0, "kept": 0, "results_tables": 0, "tables": 0, "errors": 0}

        async def one(doc):
            async with sem:
                t0 = time.time()
                try:
                    obj = await asyncio.to_thread(
                        s3.get_object, Bucket=bucket, Key=f"rags/{args.project_id}/outputs/json/{doc['filename']}.json")
                    content = json.loads(obj["Body"].read()).get("content_list") or []
                    out = await extract_document(content, args.model, os.environ["OPENROUTER_API_KEY"])
                except Exception as e:
                    totals["errors"] += 1
                    print(f"  ✗ {doc['filename'][:60]}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                    return
                rows = rows_for(args.project_id, doc, out, args.model)
                await db.delete("/effect_estimates", params={"rag_project_id": f"eq.{args.project_id}",
                                                             "doc_key": f"eq.{doc['filename']}", "source": f"eq.{SOURCE}"})
                for i in range(0, len(rows), 500):
                    r = await db.post("/effect_estimates", json=rows[i:i + 500], headers={"Prefer": "return=minimal"})
                    if r.status_code >= 400:
                        totals["errors"] += 1
                        print(f"  ✗ {doc['filename'][:60]}: insert {r.status_code}: {r.text[:300]}", flush=True)
                        return
                totals["docs"] += 1
                totals["estimates"] += len(out["estimates"])
                totals["kept"] += len(rows)
                totals["tables"] += len(out["tables"])
                totals["results_tables"] += sum(t["results_table"] for t in out["tables"])
                print(f"  {doc['filename'][:60]:60} tables {len(out['tables']):3} results "
                      f"{sum(t['results_table'] for t in out['tables']):3} kept {len(rows):4} ({time.time() - t0:.0f}s)", flush=True)

        await asyncio.gather(*(one(d) for d in docs))
    print(json.dumps(totals))


if __name__ == "__main__":
    asyncio.run(main())
