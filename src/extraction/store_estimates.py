"""
Extract effect estimates from processed documents and store them, embedded, in
effect_estimates (roadmap N6). Used by scripts/extract_estimates.py and by the Modal
pipeline after new documents are processed.

Needs SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, the R2_* variables, OPENROUTER_API_KEY
and COHERE_API_KEY. About 2.5 US cents per document with Haiku 5.5.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

import httpx

from src.extraction.table_estimates import extract_document

SOURCE = "tables_v1"
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
DOC_CONCURRENCY = 4
INSERT_BATCH = 50  # rows carry 1536-d vectors, and the small Supabase instance drops large writes


def _finite(x: Any) -> Optional[float]:
    return x if isinstance(x, (int, float)) and math.isfinite(x) else None


def _clean(v: Any) -> Any:
    return v.replace("\x00", "") if isinstance(v, str) else v


def estimate_text(r: Dict[str, Any]) -> str:
    """The text embedded for an estimate: outcome, arm and subgroup."""
    parts = [r["outcome_name"]]
    if r.get("treatment_arm"):
        parts.append(f"arm: {r['treatment_arm']}")
    if r.get("subgroup"):
        parts.append(f"subgroup: {r['subgroup']}")
    return " | ".join(parts)


def rows_for(project_id: str, doc: Dict[str, Any], out: Dict[str, Any], model: str) -> List[Dict[str, Any]]:
    """Grounded estimates with a number, in the effect_estimates shape (without embeddings)."""
    rows = []
    for e in out["estimates"]:
        if not e["grounded"] or _finite(e["effect_size"]) is None:
            continue
        ci = f"[{e['ci_low']}, {e['ci_high']}]" if e["ci_low"] is not None else None
        p = _finite(e["p_value"])
        n = _finite(e["sample_size"])
        rows.append({
            "rag_project_id": project_id, "document_id": doc["id"], "doc_key": doc["filename"], "source": SOURCE,
            "table_number": e["table_label"][:120], "outcome_name": (e["outcome"] or e["row_label"] or "?")[:500],
            "treatment_arm": e["arm"] or None, "subgroup": e["subgroup"] or None,
            "effect_size": e["effect_size"], "standard_error": _finite(e["standard_error"]),
            "p_value": p if p is not None and 0 <= p <= 1 else None,
            "p_text": ("*" * e["stars"]) if e["stars"] else None, "ci_text": ci,
            "sample_size": int(n) if n is not None and abs(n) < 2**31 and n == int(n) else None,
            "literal_text": (e["estimate_cell"] + (" " + e["se_cell"] if e["se_cell"] else ""))[:500],
            "text_position": f"{e['table_label']}, row '{e['row_label']}', column '{e['column_label']}'"[:500],
            "page": e["page"], "extraction_method": model,
        })
    return [{k: _clean(v) for k, v in r.items()} for r in rows]


def _r2():
    import boto3

    return boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")


async def _post(db: httpx.AsyncClient, rows: List[Dict[str, Any]]) -> Optional[str]:
    """Insert with retries. Returns an error message, or None."""
    last = ""
    for attempt in range(5):
        try:
            r = await db.post("/effect_estimates", json=rows, headers={"Prefer": "return=minimal"})
            if r.status_code < 400:
                return None
            last = f"insert {r.status_code}: {r.text[:300]}"
            if r.status_code < 500:
                return last
        except httpx.TransportError as e:
            last = f"{type(e).__name__}"
        await asyncio.sleep(5 * (attempt + 1))
    return last


async def extract_and_store(
    project_id: str,
    doc_keys: Optional[Iterable[str]] = None,
    model: str = DEFAULT_MODEL,
    skip_done: bool = False,
    log: Callable[[str], None] = print,
) -> Dict[str, int]:
    """
    Extract, embed and store estimates for a project's completed documents (all of them,
    or only `doc_keys`). A document's earlier rows of this source are replaced.
    """
    from src.retrieval.study_cards import embed_documents

    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    bucket, s3 = os.environ.get("R2_BUCKET_NAME", "devchat-pdfs"), _r2()
    wanted = set(doc_keys) if doc_keys is not None else None
    totals = {"docs": 0, "estimates": 0, "kept": 0, "results_tables": 0, "tables": 0, "errors": 0}

    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=120) as db:
        docs = (await db.get("/documents", params={
            "select": "id,filename", "rag_project_id": f"eq.{project_id}", "status": "eq.completed"})).json()
        if wanted is not None:
            docs = [d for d in docs if d["filename"] in wanted]
        if skip_done:
            have = (await db.get("/effect_estimates", params={
                "select": "doc_key", "rag_project_id": f"eq.{project_id}", "source": f"eq.{SOURCE}",
                "limit": "100000"})).json()
            done = {h["doc_key"] for h in have}
            docs = [d for d in docs if d["filename"] not in done]
        log(f"Estimates: {len(docs)} documents to extract")
        sem = asyncio.Semaphore(DOC_CONCURRENCY)

        async def one(doc: Dict[str, Any]) -> None:
            async with sem:
                t0 = time.time()
                name = doc["filename"]
                try:
                    obj = await asyncio.to_thread(
                        s3.get_object, Bucket=bucket, Key=f"rags/{project_id}/outputs/json/{name}.json")
                    content = json.loads(obj["Body"].read()).get("content_list") or []
                    out = await extract_document(content, model, os.environ["OPENROUTER_API_KEY"])
                    rows = rows_for(project_id, doc, out, model)
                    if rows:
                        vectors = await asyncio.to_thread(embed_documents, [estimate_text(r) for r in rows])
                        for r, v in zip(rows, vectors):
                            r["embedding"] = [float(x) for x in v]
                except Exception as e:
                    totals["errors"] += 1
                    log(f"  ✗ {name[:60]}: {type(e).__name__}: {str(e)[:120]}")
                    return
                await db.delete("/effect_estimates", params={
                    "rag_project_id": f"eq.{project_id}", "doc_key": f"eq.{name}", "source": f"eq.{SOURCE}"})
                for i in range(0, len(rows), INSERT_BATCH):
                    err = await _post(db, rows[i:i + INSERT_BATCH])
                    if err:
                        totals["errors"] += 1
                        log(f"  ✗ {name[:60]}: {err}")
                        return
                results = sum(t["results_table"] for t in out["tables"])
                totals["docs"] += 1
                totals["estimates"] += len(out["estimates"])
                totals["kept"] += len(rows)
                totals["tables"] += len(out["tables"])
                totals["results_tables"] += results
                log(f"  {name[:60]:60} tables {len(out['tables']):3} results {results:3} "
                    f"kept {len(rows):4} ({time.time() - t0:.0f}s)")

        await asyncio.gather(*(one(d) for d in docs))
    return totals
