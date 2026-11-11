"""
Group a collection's programme names into distinct programmes (roadmap N6 step 3).

Each document's study facts name its programme in the document's own words, so one
programme appears under several names (BRAC's CFPR, CFPR-TUP, TUP and "BRAC Ultra Poor
Programme" in Bangladesh). One model call over the collection's names assigns each
document a canonical programme, stored as facts["programme_group"], so counts and
medians take each programme once. About one US cent per collection.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict

import httpx

from src.extraction.store_estimates import DEFAULT_MODEL
from src.extraction.table_estimates import _chat, _parse_json

PROMPT = """Below are the programmes evaluated by the documents of one evidence collection, one per
line as "id | programme name as the document gives it | countries". Group them into distinct
programmes.

Rules:
- The same programme run by the same implementer in the same country is ONE programme, even when
  documents use different names, acronyms, phases or evaluation rounds (for example BRAC's CFPR,
  CFPR/TUP, TUP and "Ultra Poor Programme" in Bangladesh are one programme).
- The same model run in a different country, or by a different implementer, is a different
  programme. A multi-country evaluation is its own programme.
- Name each group briefly with its country, e.g. "BRAC TUP/CFPR, Bangladesh".
- Every id must appear in exactly one group.

PROGRAMMES:
{lines}

Return JSON only: {{"groups": [{{"name": "...", "ids": [1, 2]}}]}}"""


async def group_programmes(
    project_id: str, model: str = DEFAULT_MODEL, log: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """Assign facts["programme_group"] for every document of a project. Returns counts."""
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=120) as db:
        rows = (await db.get("/study_facts", params={
            "select": "id,rag_project_id,doc_key,facts", "rag_project_id": f"eq.{project_id}",
            "limit": "10000"})).json()
        named = [r for r in rows if (r["facts"].get("programme") or "").strip()]
        if not named:
            return {"documents": len(rows), "groups": 0}
        lines = "\n".join(f"{i + 1} | {r['facts']['programme']} | {', '.join(r['facts'].get('countries') or [])}"
                          for i, r in enumerate(named))
        async with httpx.AsyncClient(timeout=300, headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}) as llm:
            data = _parse_json(await _chat(llm, model, PROMPT.format(lines=lines)))
        name_of: Dict[int, str] = {}
        for g in data.get("groups") or []:
            for i in g.get("ids") or []:
                try:
                    name_of.setdefault(int(i), str(g.get("name") or "").strip())
                except (TypeError, ValueError):
                    continue
        updates = []
        for i, r in enumerate(named):
            group = name_of.get(i + 1) or r["facts"]["programme"]
            updates.append({"id": r["id"], "rag_project_id": r["rag_project_id"], "doc_key": r["doc_key"],
                            "facts": {**r["facts"], "programme_group": group}})
        for i in range(0, len(updates), 100):
            resp = await db.post("/study_facts", params={"on_conflict": "id"}, json=updates[i:i + 100],
                                 headers={"Prefer": "return=minimal,resolution=merge-duplicates"})
            resp.raise_for_status()
    groups = len({u["facts"]["programme_group"] for u in updates})
    log(f"Programme groups: {len(named)} documents in {groups} programmes")
    return {"documents": len(named), "groups": groups, "unassigned": len(named) - len(name_of)}


if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    print(json.dumps(asyncio.run(group_programmes(sys.argv[1]))))
