"""
Study facts: one structured record per document (roadmap N6 step 3).

Some questions need facts compared across studies, not passages: which programmes put
women first as recipients, what a programme cost per beneficiary, the benefit-cost
ratio, the headline income gain as a share of the comparison group. One model call
reads the whole document (Docling text and tables, with page markers) and fills a
fixed form. Every figure must come with a verbatim quote, and a figure is kept only
if its quote is found in the document and contains the number.

The answer step computes medians and group comparisons from these records in code
(src/agents/study_synthesis.py), so the model never does the arithmetic.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import httpx

from src.extraction.secondhand import cites_other_study
from src.extraction.table_estimates import OPENROUTER_URL, _chat, _norm, _parse_json, parse_number

MAX_DOC_CHARS = 400_000  # about 100k tokens: whole papers, cut only for very long reports

PROMPT = """You read one document from a collection of evidence on a development programme, and
fill a fixed form about it. Use only what the document says. Every figure needs a quote copied
EXACTLY from the document (a phrase or sentence, at most 300 characters) that contains it, and the
page number from the [p. N] markers. Leave a field empty rather than guess.

FORM (return JSON only):
{{
  "is_impact_evaluation": true if the document reports its own estimates of a programme's effects,
  "programme": "<short name of the programme with its country, e.g. 'BRAC TUP, Bangladesh'; '' if none>",
  "countries": ["<country>", ...],
  "women_main_recipients": "yes" if transfers or participation go mainly to women, "no" if mainly to
      men or to households without a gender focus, "mixed", or "not_stated",
  "women_quote": "<quote supporting women_main_recipients, '' if not_stated>",
  "components": [any of "asset_transfer", "cash_transfer", "consumption_support", "coaching",
      "savings", "training", "health", "financial_inclusion", "group_formation"],
  "cost_per_beneficiary": [{{"amount": "<number as printed>", "currency": "<e.g. USD, PPP USD, ETB>",
      "price_year": "<year or ''>", "unit": "<per household, per participant, ...>",
      "quote": "...", "page": N}}]  (the TOTAL cost of the programme per beneficiary, all components
      and delivery included; not the value of the transfer alone),
  "transfer_value": [{{"amount": "<number as printed>", "currency": "...", "price_year": "...",
      "unit": "...", "quote": "...", "page": N}}]  (the value of the asset or cash transfer given to each
      beneficiary),
  "benefit_cost": [{{"ratio": "<benefit-cost ratio as printed, e.g. 1.33 or 133%>",
      "horizon_years": "<years or ''>", "quote": "...", "page": N}}],
  "headline_effects": [{{"outcome": one of "income", "consumption", "assets", "savings",
      "food_security", "poverty", "employment", "wellbeing", "other",
      "outcome_label": "<as the document names it>",
      "direction": "increase", "decrease" or "no_change",
      "percent_change": "<the relative effect as a percentage of the comparison group or baseline, as
          printed, e.g. 12 or 12%; '' if not reported as a percentage. Percentage points are not
          a percentage change: leave '' for them>",
      "months_after_start": "<months from the start of the programme to measurement; '' if unclear>",
      "significant": "yes", "no" or "not_stated",
      "quote": "...", "page": N}}],
  "followup_months": [<months after the start of the programme of each survey round, numbers>]
}}

Report only figures about the programme THIS document evaluates, from its own data. Never report
figures the document cites from other studies (its literature review or comparisons with earlier
evaluations): leave those out entirely. A document that only reviews other studies has
is_impact_evaluation false and no costs, ratios or effects.
Report at most six headline effects, the ones the document itself presents as its main findings.
Only report a percent_change the document states (do not compute one).

DOCUMENT:
{document}"""


def document_text(content_list: List[Dict[str, Any]], limit: int = MAX_DOC_CHARS) -> str:
    """The document as text with [p. N] markers before each new page, tables included."""
    out, page, size = [], None, 0
    for item in content_list:
        kind = item.get("type")
        if kind not in ("text", "title", "table"):
            continue
        text = str(item.get("text") or item.get("table_body") or "").strip()
        if not text:
            continue
        p = item.get("page_idx")
        if p not in (None, "") and p != page:
            page = p
            out.append(f"\n[p. {p}]")
        out.append(text)
        size += len(text)
        if size > limit:
            out.append("\n[document cut for length]")
            break
    return "\n".join(out)


def _quote_ok(quote: str, norm_doc: str) -> bool:
    q = _norm(quote)
    # A quote that cites another study reports secondhand evidence: never kept (rule, 11 Nov 2026)
    return len(q) >= 8 and q in norm_doc and not cites_other_study(quote)


def _number_in(value: str, quote: str) -> Optional[float]:
    """The value as a number, if that number appears in its quote."""
    x = parse_number(str(value))
    if x is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value).split("%")[0])
    return x if digits and digits in re.sub(r"[^\d]", "", quote) else None


def _int(value: Any) -> Optional[int]:
    x = parse_number(str(value)) if value not in (None, "") else None
    return int(x) if x is not None and 0 < x < 1000 else None


def _year(value: Any) -> Optional[int]:
    m = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", str(value or ""))
    return int(m.group(1)) if m else None


def ground(raw: Dict[str, Any], doc_text: str) -> Dict[str, Any]:
    """Keep only figures whose quote is in the document and contains the figure."""
    norm_doc = _norm(doc_text)
    women = str(raw.get("women_main_recipients") or "not_stated").lower()
    if women not in ("yes", "no", "mixed", "not_stated"):
        women = "not_stated"
    women_quote = str(raw.get("women_quote") or "")
    if women != "not_stated" and not _quote_ok(women_quote, norm_doc):
        women, women_quote = "not_stated", ""

    def money(items: Any) -> List[Dict[str, Any]]:
        out = []
        for c in items or []:
            quote = str(c.get("quote") or "")
            amount = _number_in(c.get("amount", ""), quote)
            if amount is not None and amount > 0 and _quote_ok(quote, norm_doc):
                out.append({"amount": amount, "currency": str(c.get("currency") or "").strip(),
                            "price_year": _year(c.get("price_year")),
                            "unit": str(c.get("unit") or ""), "quote": quote, "page": c.get("page")})
        return out

    costs = money(raw.get("cost_per_beneficiary"))
    transfers = money(raw.get("transfer_value"))

    ratios = []
    for b in raw.get("benefit_cost") or []:
        quote = str(b.get("quote") or "")
        value = _number_in(b.get("ratio", ""), quote)
        if value is None or not _quote_ok(quote, norm_doc):
            continue
        if "%" in str(b.get("ratio")) or value > 20:
            value = value / 100  # 133% means a ratio of 1.33
        ratios.append({"ratio": round(value, 3), "horizon_years": _int(b.get("horizon_years")),
                       "quote": quote, "page": b.get("page")})

    effects = []
    for e in (raw.get("headline_effects") or [])[:6]:
        quote = str(e.get("quote") or "")
        if not _quote_ok(quote, norm_doc):
            continue
        pct = _number_in(e.get("percent_change", ""), quote) if e.get("percent_change") not in (None, "") else None
        direction = str(e.get("direction") or "").lower()
        if pct is not None and ("percentage point" in quote.lower() and "%" not in quote):
            pct = None  # points, not a relative change
        if pct is not None and direction == "decrease":
            pct = -abs(pct)
        sig = str(e.get("significant") or "not_stated").lower()
        effects.append({"outcome": str(e.get("outcome") or "other").lower(),
                        "direction": direction if direction in ("increase", "decrease", "no_change") else "",
                        "outcome_label": str(e.get("outcome_label") or ""),
                        "percent_change": pct, "months_after_start": _int(e.get("months_after_start")),
                        "significant": sig if sig in ("yes", "no") else "not_stated",
                        "quote": quote, "page": e.get("page")})

    followups = sorted({m for m in (_int(x) for x in raw.get("followup_months") or []) if m})
    return {
        "is_impact_evaluation": bool(raw.get("is_impact_evaluation")),
        "programme": str(raw.get("programme") or "")[:120],
        "countries": [str(c) for c in (raw.get("countries") or []) if c][:12],
        "women_main_recipients": women, "women_quote": women_quote,
        "components": [str(c) for c in (raw.get("components") or [])][:10],
        "cost_per_beneficiary": costs, "transfer_value": transfers, "benefit_cost": ratios, "headline_effects": effects,
        "followup_months": followups,
    }


async def extract_facts(content_list: List[Dict[str, Any]], model: str, api_key: str) -> Dict[str, Any]:
    """One call for the whole document, then grounding. Returns the grounded facts."""
    text = document_text(content_list)
    async with httpx.AsyncClient(timeout=300, headers={"Authorization": f"Bearer {api_key}"}) as client:
        reply = await _chat(client, model, PROMPT.format(document=text))
    try:
        raw = _parse_json(reply)
    except (ValueError, json.JSONDecodeError):
        raw = {}
    return ground(raw, text)


__all__ = ["OPENROUTER_URL", "document_text", "extract_facts", "ground"]
