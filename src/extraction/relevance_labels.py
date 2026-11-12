"""
Label every paragraph of a document by its role (prototype for the filtered index, 11 Nov 2026).

The model only labels paragraphs by number and never rewrites them, so kept text stays
verbatim, with its page, for quotes and PDF highlighting. Paragraphs labelled as this
study's evidence are kept for chunking and embedding. Other studies' findings are kept
apart so they are never cited as the paper's own. Background and boilerplate are dropped.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List

import httpx

from src.extraction.table_estimates import _chat, _parse_json

LABELS = {
    "A": "abstract",          # abstract, executive summary or summary of key findings of THIS study
    "F": "own_finding",       # this study's own results, estimates, effects, results tables
    "M": "method",            # design, sample, data, identification, measurement, estimation
    "I": "intervention",      # what the programme gave, to whom, how it was delivered
    "S": "setting",           # country, population, baseline characteristics, descriptive tables
    "C": "cost",              # costs, cost-effectiveness, benefit-cost
    "L": "limitation",        # caveats, threats to validity, attrition, what the study cannot say
    "O": "other_study",       # findings or claims of OTHER studies (literature review, comparisons)
    "B": "background",        # general context, policy motivation, theory, without this study's evidence
    "X": "boilerplate",       # references, acknowledgements, contents, headers, footers, disclaimers
}
KEEP = {"abstract", "own_finding", "method", "intervention", "setting", "cost", "limitation"}
BATCH = 80
MAX_UNIT_CHARS = 1500
CONCURRENCY = 8

PROMPT = """You label the paragraphs of one research document by their role, so that the document's own
evidence can be separated from noise.

DOCUMENT: {title}

Codes:
A = the abstract, executive summary or summary of key findings of THIS study
F = this study's OWN results: effects, estimates, comparisons of its treatment and control groups,
    results tables, its own conclusions about its results
M = this study's method: design, sampling, data, identification, measurement, estimation
I = the intervention evaluated: what was given, to whom, how it was delivered and for how long
S = setting and population: country, region, who the participants are, baseline or descriptive data
C = costs, cost-effectiveness or benefit-cost figures of the programme
L = limitations, caveats, attrition, threats to validity
O = results or claims of OTHER studies (literature review, comparisons with earlier work); use O even
    when the sentence gives numbers, if they come from another study
B = general background, policy context, motivation or theory with no evidence from this study
X = boilerplate: reference lists, acknowledgements, table of contents, page headers or footers,
    author notes, disclaimers, figure placeholders

A TABLE that reports this study's effects, impacts, estimates or regression results is F, never X,
even when it has many numbers and few words.
A paragraph that mixes roles gets the code of its most important content for an evidence review
(F before C, M, I, S, L; O only if it mainly reports other studies).

PARAGRAPHS:
{units}

Return JSON only, one code per paragraph number: {{"labels": {{"<number>": "<code>", ...}}}}"""


def units_from_content(content_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Text, title and table items as labellable units, in document order."""
    units = []
    for i, item in enumerate(content_list):
        kind = item.get("type")
        if kind not in ("text", "title", "table"):
            continue
        text = str(item.get("text") or item.get("table_body") or "").strip()
        if text:
            p = item.get("page_idx")
            units.append({"index": i, "kind": kind, "page": int(p) + 1 if p not in (None, "") else None,
                          "text": text})
    return units


_RESULTS_CAPTION = re.compile(r"\b(effects?|impacts?|estimates?|regressions?|treatment|ITT|ATE|LATE|IV)\b", re.I)


def keep_results_tables(units: List[Dict[str, Any]], labels: List[str], estimate_tables: set) -> List[str]:
    """
    Rule after labelling: a table is this study's own finding when estimates were extracted
    from it (indexes in `estimate_tables`) or its caption names effects or estimates. The model
    labelled 7 such tables boilerplate in the Paraguay paper (11 Nov 2026).
    """
    out = list(labels)
    for k, u in enumerate(units):
        if u["kind"] != "table" or out[k] in ("own_finding", "cost"):
            continue
        first_line = u["text"].splitlines()[0][:200] if u["text"] else ""
        if k in estimate_tables or (_RESULTS_CAPTION.search(first_line) and out[k] in ("boilerplate", "background", "unlabelled")):
            out[k] = "own_finding"
    return out


def _title(units: List[Dict[str, Any]]) -> str:
    for u in units[:15]:
        if u["kind"] == "title" and len(u["text"]) > 15:
            return u["text"][:200]
    return units[0]["text"][:200] if units else ""


async def label_units(units: List[Dict[str, Any]], model: str, api_key: str) -> List[str]:
    """One label name per unit ('unlabelled' where the model gave none)."""
    title = _title(units)
    sem = asyncio.Semaphore(CONCURRENCY)
    labels: List[str] = ["unlabelled"] * len(units)

    async with httpx.AsyncClient(timeout=300, headers={"Authorization": f"Bearer {api_key}"}) as client:
        async def batch(start: int) -> None:
            chunk = units[start:start + BATCH]
            lines = "\n".join(
                f"[{start + k + 1}] ({'TABLE' if u['kind'] == 'table' else 'p. ' + str(u['page'])}) "
                f"{u['text'][:MAX_UNIT_CHARS]}" for k, u in enumerate(chunk))
            async with sem:
                try:
                    data = _parse_json(await _chat(client, model, PROMPT.format(title=title, units=lines)))
                except (ValueError, json.JSONDecodeError, httpx.HTTPError):
                    return
            for key, code in (data.get("labels") or {}).items():
                try:
                    n = int(str(key).strip("[] ")) - 1
                except ValueError:
                    continue
                if start <= n < start + len(chunk):
                    labels[n] = LABELS.get(str(code).strip().upper()[:1], "unlabelled")

        await asyncio.gather(*(batch(s) for s in range(0, len(units), BATCH)))
    return labels
