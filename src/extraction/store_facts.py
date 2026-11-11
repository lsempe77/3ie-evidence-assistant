"""
Extract study facts (src/extraction/study_facts.py) for a project's processed documents
and store them in study_facts, one row per document. Used by scripts/extract_facts.py
and by the Modal pipeline after new documents are processed.

Needs SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, the R2_* variables and OPENROUTER_API_KEY.
About one US cent per document with Haiku 5.5.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Callable, Dict, Iterable, Optional

import httpx

from src.extraction.store_estimates import DEFAULT_MODEL, _r2
from src.extraction.study_facts import extract_facts

DOC_CONCURRENCY = 6


async def extract_and_store_facts(
    project_id: str,
    doc_keys: Optional[Iterable[str]] = None,
    model: str = DEFAULT_MODEL,
    skip_done: bool = False,
    log: Callable[[str], None] = print,
) -> Dict[str, int]:
    """Extract and upsert facts for a project's completed documents (all, or only `doc_keys`)."""
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    bucket, s3 = os.environ.get("R2_BUCKET_NAME", "devchat-pdfs"), _r2()
    wanted = set(doc_keys) if doc_keys is not None else None
    totals = {"docs": 0, "evaluations": 0, "with_cost": 0, "with_percent_effect": 0, "errors": 0}

    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=120) as db:
        docs = (await db.get("/documents", params={
            "select": "id,filename", "rag_project_id": f"eq.{project_id}", "status": "eq.completed"})).json()
        if wanted is not None:
            docs = [d for d in docs if d["filename"] in wanted]
        if skip_done:
            have = (await db.get("/study_facts", params={
                "select": "doc_key", "rag_project_id": f"eq.{project_id}", "limit": "100000"})).json()
            done = {h["doc_key"] for h in have}
            docs = [d for d in docs if d["filename"] not in done]
        log(f"Study facts: {len(docs)} documents to read")
        sem = asyncio.Semaphore(DOC_CONCURRENCY)

        async def one(doc: Dict[str, Any]) -> None:
            async with sem:
                t0, name = time.time(), doc["filename"]
                try:
                    obj = await asyncio.to_thread(
                        s3.get_object, Bucket=bucket, Key=f"rags/{project_id}/outputs/json/{name}.json")
                    content = json.loads(obj["Body"].read()).get("content_list") or []
                    facts = await extract_facts(content, model, os.environ["OPENROUTER_API_KEY"])
                    r = await db.post("/study_facts", params={"on_conflict": "rag_project_id,doc_key"},
                                      headers={"Prefer": "return=minimal,resolution=merge-duplicates"},
                                      json=[{"rag_project_id": project_id, "document_id": doc["id"], "doc_key": name,
                                             "facts": facts, "model": model}])
                    r.raise_for_status()
                except Exception as e:
                    totals["errors"] += 1
                    log(f"  ✗ {name[:60]}: {type(e).__name__}: {str(e)[:160]}")
                    return
                totals["docs"] += 1
                totals["evaluations"] += bool(facts["is_impact_evaluation"])
                totals["with_cost"] += bool(facts["cost_per_beneficiary"])
                totals["with_percent_effect"] += any(e["percent_change"] is not None for e in facts["headline_effects"])
                log(f"  {name[:60]:60} {facts['programme'][:40]:40} women {facts['women_main_recipients']:10} "
                    f"costs {len(facts['cost_per_beneficiary'])} effects {len(facts['headline_effects'])} "
                    f"({time.time() - t0:.0f}s)")

        await asyncio.gather(*(one(d) for d in docs))
    return totals
