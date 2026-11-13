"""
Side-by-side viewer: the full parsed paper against what the extraction keeps (11 Nov 2026).

Left: every paragraph and table of the Docling output, with the role the labeller gave it
(src/extraction/relevance_labels.py). Right: the text kept for the filtered index (a gap
where a paragraph is dropped), and the study facts and table estimates extracted from that
paragraph. Each row has "Useful" and "Noise" buttons; judgements stay in the browser and
can be exported as JSON, as a hand-labelled set to check the labeller against.

    python evaluation/label_viewer.py --project-id <uuid> --labels <label_check.json>
        --docs <doc.json> [<doc.json> ...] --out viewer.html

The page holds the papers' full text: keep it local, do not publish it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.extraction.relevance_labels import KEEP, units_from_content  # noqa: E402


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).replace("−", "-").replace("–", "-").lower()


def _find_unit(units: List[Dict[str, Any]], quote: str, page: Optional[int]) -> Optional[int]:
    q = _norm(quote)
    if q:
        for k, u in enumerate(units):
            if q in u["_norm"]:
                return k
        head = q[:40]
        for k, u in enumerate(units):
            if head and head in u["_norm"]:
                return k
    if isinstance(page, int):
        for k, u in enumerate(units):
            if u["page"] == page:
                return k
    return None


def _table_unit(units: List[Dict[str, Any]], cell: str, page: Optional[int]) -> Optional[int]:
    c = _norm(cell)
    on_page = [k for k, u in enumerate(units) if u["kind"] == "table" and u["page"] == page]
    for k in on_page:
        if c and c in units[k]["_norm"]:
            return k
    if on_page:
        return on_page[0]
    tables = [k for k, u in enumerate(units) if u["kind"] == "table" and c and c in u["_norm"]]
    return tables[0] if tables else None


def fetch(db: httpx.Client, project_id: str, doc_key: str) -> tuple:
    facts = db.get("/study_facts", params={"select": "facts", "rag_project_id": f"eq.{project_id}",
                                           "doc_key": f"eq.{doc_key}"}).json()
    estimates = db.get("/effect_estimates", params={
        "select": "outcome_name,treatment_arm,subgroup,literal_text,page,table_number,p_text,sample_size",
        "rag_project_id": f"eq.{project_id}", "doc_key": f"eq.{doc_key}", "source": "eq.tables_v1",
        "limit": "5000"}).json()
    return (facts[0]["facts"] if facts else {}), estimates


def build_doc(path: Path, labels: List[str], facts: Dict[str, Any], estimates: List[Dict[str, Any]]) -> Dict[str, Any]:
    content = json.loads(path.read_text(encoding="utf-8")).get("content_list") or []
    units = units_from_content(content)
    if len(units) != len(labels):
        raise SystemExit(f"{path.name}: {len(units)} paragraphs but {len(labels)} labels")
    for u in units:
        u["_norm"] = _norm(u["text"])
    extra: Dict[int, List[Dict[str, str]]] = {}

    def add(k: Optional[int], kind: str, text: str) -> None:
        if k is not None:
            extra.setdefault(k, []).append({"kind": kind, "text": text})

    if facts.get("women_main_recipients") not in (None, "not_stated"):
        add(_find_unit(units, facts.get("women_quote", ""), None), "fact",
            f"Women as main recipients: {facts['women_main_recipients']}")
    for c in facts.get("cost_per_beneficiary") or []:
        add(_find_unit(units, c.get("quote", ""), c.get("page")), "fact",
            f"Cost per beneficiary: {c['amount']:,.0f} {c.get('currency', '')} {c.get('unit', '')}".strip())
    for c in facts.get("transfer_value") or []:
        add(_find_unit(units, c.get("quote", ""), c.get("page")), "fact",
            f"Transfer value: {c['amount']:,.0f} {c.get('currency', '')}".strip())
    for b in facts.get("benefit_cost") or []:
        add(_find_unit(units, b.get("quote", ""), b.get("page")), "fact",
            f"Benefit-cost ratio: {b['ratio']}" + (f" over {b['horizon_years']} years" if b.get("horizon_years") else ""))
    for e in facts.get("headline_effects") or []:
        pct = f" ({e['percent_change']:+g}%)" if e.get("percent_change") is not None else ""
        add(_find_unit(units, e.get("quote", ""), e.get("page")), "fact",
            f"Headline effect, {e.get('outcome')}: {e.get('outcome_label', '')}{pct}, significant: {e.get('significant')}")
    for est in estimates:
        cell = (est.get("literal_text") or "").split(" (")[0].split(" [")[0]
        who = "; ".join(x for x in (est.get("treatment_arm"), est.get("subgroup")) if x)
        add(_table_unit(units, cell, est.get("page")), "estimate",
            f"{est.get('outcome_name')}{f' ({who})' if who else ''}: {est.get('literal_text')}")

    title = next((u["text"] for u in units[:15] if u["kind"] == "title" and len(u["text"]) > 15), path.stem)
    return {
        "key": path.stem, "title": title[:200],
        "programme": facts.get("programme", ""), "countries": facts.get("countries", []),
        "units": [{"i": k, "page": u["page"], "kind": u["kind"], "label": lab, "kept": lab in KEEP,
                   "text": u["text"], "extra": extra.get(k, [])} for k, (u, lab) in enumerate(zip(units, labels))],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--docs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    labelled = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    docs = []
    with httpx.Client(base_url=url, headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=120) as db:
        for p in map(Path, args.docs):
            match = [k for k in labelled if p.name.startswith(k) or k.startswith(p.stem)]
            if not match:
                raise SystemExit(f"no labels for {p.name}")
            facts, estimates = fetch(db, args.project_id, p.stem)
            docs.append(build_doc(p, labelled[match[0]]["labels"], facts, estimates))
    template = (ROOT / "evaluation" / "label_viewer_template.html").read_text(encoding="utf-8")
    data = json.dumps(docs, ensure_ascii=False).replace("</", "<\\/")
    Path(args.out).write_text(template.replace("/*__DATA__*/[]", data), encoding="utf-8")
    print(f"{args.out}: {len(docs)} papers, {sum(len(d['units']) for d in docs)} paragraphs")


if __name__ == "__main__":
    main()
