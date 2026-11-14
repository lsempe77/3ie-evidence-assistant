"""
Extract treatment-effect estimates from a document's tables (roadmap N6 step 2).

Works on the parser output saved for every document (Docling `content_list`: each
table as Markdown with its page and caption). Per table, one model call decides
whether it is a results table and, if so, lists its estimates with the cells copied
verbatim. Numbers are then parsed from those cells by tested code (parse_number,
parse_estimate_cell), and a row is kept only if its cells appear in the table, so a
figure the model did not read from the table cannot get in.

Why not reuse what exists: the graduation review's 2025 extraction found 8 and the
repo's rule-based V6 pipeline 9 of the review's 20 hand-extracted estimates
(evaluation/check_estimates_vs_human.py), failing on different studies.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CONTEXT_ITEMS = 2          # text items before and after a table that travel with it
MAX_TABLE_CHARS = 24000
TABLE_CONCURRENCY = 8

PROMPT = """You extract treatment-effect estimates from one table of an impact evaluation.

TEXT AROUND THE TABLE (caption, notes, nearby paragraphs):
{context}

TABLE (Markdown, page {page}):
{table}

INFERRED STRUCTURE (from the headers, notes and arithmetic; may be empty or wrong, and the table itself wins):
{structure}

First decide: does this table report estimated effects of a programme or treatment, such as
regression coefficients, differences between treatment and control (or before and after),
impact estimates or marginal effects? Descriptive statistics, sample descriptions, balance
tests, attrition tables and lists of variables are NOT results tables.

If it is a results table, list every estimate of a treatment effect on an outcome. For each:
- outcome: the outcome as the table names it (row or column label), with units if given
- arm: the treatment or comparison the estimate refers to (e.g. "Full graduation package",
  "TUP vs control", "Endline"); "" if there is only one
- subgroup: the subgroup if the estimate is for one (e.g. "Women", "Bangladesh"); "" otherwise
- row_label and column_label: exactly as printed
- estimate_cell: the cell holding the estimate, copied EXACTLY as printed (keep stars, commas,
  signs and spacing)
- se_cell: the cell holding its standard error, t-statistic or confidence interval, copied
  exactly ("" if none). Often the next row, in parentheses or brackets.
- se_kind: "se", "t", "ci" or "" (from the notes; parentheses are usually SEs)
- p_cell: an exact p-value cell if the table has one, else ""
- n: the number of observations for the estimate if the table gives it, else ""

Do not include estimates the table reproduces from OTHER studies (for example a comparison with
earlier evaluations): only this study's own estimates.
Do not include control-group means, constants, covariates or controls, baseline levels,
first-stage coefficients, R-squared or sample sizes as estimates.

Return JSON only:
{{"results_table": true or false, "table_label": "<e.g. Table 3>", "estimates": [ ... ]}}"""


# ----------------------------------------------------------------- number parsing

_STARS = re.compile(r"\*+|†+|‡+")
_NUM = re.compile(r"[-−–]?\s?\d[\d.,]*")


def parse_number(text: str) -> Optional[float]:
    """
    The first number in `text`, reading separators as a person would:
    "4,408" is 4408 (thousands), "0,84" is 0.84 (decimal comma), "1.234,5" is 1234.5,
    "−0.18***" is -0.18. Returns None when there is no number.
    """
    if text is None:
        return None
    s = _STARS.sub("", str(text)).replace("−", "-").replace("–", "-")
    m = _NUM.search(s)
    if not m:
        return None
    tok = m.group(0).replace(" ", "")
    neg = tok.startswith("-")
    tok = tok.lstrip("-").rstrip(".,")
    if "," in tok and "." in tok:
        # whichever comes last is the decimal mark
        if tok.rfind(",") > tok.rfind("."):
            tok = tok.replace(".", "").replace(",", ".")
        else:
            tok = tok.replace(",", "")
    elif "," in tok:
        head, _, tail = tok.rpartition(",")
        groups = tok.split(",")
        thousands = (len(tail) == 3 and head not in ("0", "") and all(len(g) == 3 for g in groups[1:])
                     and 1 <= len(groups[0]) <= 3)
        tok = tok.replace(",", "") if thousands else tok.replace(",", ".", 1).replace(",", "")
    elif tok.count(".") > 1:
        # "1.234.567" thousands with dots
        tok = tok.replace(".", "")
    try:
        value = float(tok)
    except ValueError:
        return None
    return -value if neg else value


def count_stars(text: str) -> int:
    m = re.search(r"\*+", str(text or ""))
    return len(m.group(0)) if m else 0


def parse_interval(text: str) -> Optional[tuple]:
    nums = [parse_number(x) for x in re.findall(r"[-−–]?\d[\d.,]*", str(text or ""))]
    nums = [n for n in nums if n is not None]
    return (nums[0], nums[1]) if len(nums) >= 2 else None


# ------------------------------------------------------------------- extraction


@dataclass
class Estimate:
    table_label: str
    page: Optional[int]
    outcome: str
    arm: str
    subgroup: str
    row_label: str
    column_label: str
    estimate_cell: str
    se_cell: str
    se_kind: str
    p_cell: str
    effect_size: Optional[float]
    standard_error: Optional[float]
    t_stat: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    p_value: Optional[float]
    stars: int
    sample_size: Optional[int]
    grounded: bool
    notes: List[str] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).replace("−", "-").replace("–", "-")


def to_estimate(raw: Dict[str, Any], table_label: str, page: Optional[int], table_text: str) -> Estimate:
    est_cell = str(raw.get("estimate_cell") or "")
    se_cell = str(raw.get("se_cell") or "")
    kind = str(raw.get("se_kind") or "").lower()
    if not kind and se_cell:
        kind = "ci" if "," in se_cell.strip("()[]") and parse_interval(se_cell) and "[" in se_cell else "se"
    se = t = lo = hi = None
    if kind == "ci":
        iv = parse_interval(se_cell)
        lo, hi = iv if iv else (None, None)
    elif kind == "t":
        t = parse_number(se_cell)
    elif se_cell:
        se = parse_number(se_cell)
        se = abs(se) if se is not None else None
    n = parse_number(raw.get("n"))
    table_norm = _norm(table_text)
    grounded = bool(est_cell) and _norm(est_cell) in table_norm and (not se_cell or _norm(se_cell) in table_norm)
    notes = [] if grounded else ["cell not found verbatim in the table"]
    return Estimate(
        table_label=table_label, page=page, outcome=str(raw.get("outcome") or ""),
        arm=str(raw.get("arm") or ""), subgroup=str(raw.get("subgroup") or ""),
        row_label=str(raw.get("row_label") or ""), column_label=str(raw.get("column_label") or ""),
        estimate_cell=est_cell, se_cell=se_cell, se_kind=kind, p_cell=str(raw.get("p_cell") or ""),
        effect_size=parse_number(est_cell), standard_error=se, t_stat=t, ci_low=lo, ci_high=hi,
        p_value=parse_number(raw.get("p_cell")) if raw.get("p_cell") else None,
        stars=count_stars(est_cell), sample_size=int(n) if n is not None and n.is_integer() and n > 0 else None,
        grounded=grounded, notes=notes,
    )


def table_units(content_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Each table with its page, caption and the text items just before and after it."""
    units = []
    for i, item in enumerate(content_list):
        if item.get("type") != "table":
            continue
        text = str(item.get("text") or item.get("table_body") or "")
        if "|" not in text:
            continue
        around = []
        for j in list(range(max(0, i - CONTEXT_ITEMS), i)) + list(range(i + 1, min(len(content_list), i + 1 + CONTEXT_ITEMS))):
            other = content_list[j]
            if other.get("type") != "table":
                around.append(str(other.get("text") or "")[:1500])
        caption = item.get("table_caption")
        if isinstance(caption, (list, tuple)):
            caption = " ".join(str(c) for c in caption)
        if isinstance(caption, str) and caption.startswith("["):
            try:
                caption = " ".join(json.loads(caption.replace("'", '"')))
            except ValueError:
                pass
        try:
            # Docling's page_idx counts from 0; pages shown to users count from 1, as chunks do
            page = int(item.get("page_idx")) + 1 if item.get("page_idx") not in (None, "") else None
        except (TypeError, ValueError):
            page = None
        units.append({"index": i, "page": page, "caption": caption or "", "text": text[:MAX_TABLE_CHARS],
                      "context": "\n".join(x for x in around if x.strip())})
    return units


async def _chat(client: httpx.AsyncClient, model: str, prompt: str) -> str:
    body = {"model": model, "temperature": 0, "max_tokens": 16000,
            "reasoning": {"effort": "low", "exclude": True},
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}]}
    for attempt in range(3):
        try:
            r = await client.post(OPENROUTER_URL, json=body)
            if r.status_code >= 500 or r.status_code == 429:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError):
            if attempt == 2:
                raise
            await asyncio.sleep(2 * (attempt + 1))
    return ""


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def _table_analysis(u: Dict[str, Any]):
    """Table type and inferred structure, computed before the model call (lazy imports avoid a cycle)."""
    from src.extraction.table_rules import classify_table
    from src.extraction.table_structure import ESTIMATE, LAYOUT_ROWS, interpret_table, parse_markdown_table

    grid = parse_markdown_table(u["text"])
    header = " | ".join(grid.headers[-1]) if grid.headers else ""
    kind, _ = classify_table(u.get("caption") or "", " ".join(grid.notes), header)
    result = interpret_table(u["text"], notes=f"{u.get('caption') or ''}\n{u.get('context') or ''}".strip())
    has_estimate = (ESTIMATE in result.row_roles) if result.layout == LAYOUT_ROWS else (result.estimate is not None)
    return kind, result, has_estimate


def _structure_hint(result) -> str:
    """A short description of the inferred columns, for the model prompt."""
    from src.extraction.table_structure import LAYOUT_ROWS

    parts: List[str] = []
    if result.layout == LAYOUT_ROWS:
        parts.append("statistics are in rows and outcomes or models are in the columns")
    for index, name in ((result.estimate, "estimate"), (result.se, "standard error"),
                        (result.t, "t or z statistic"), (result.p, "p-value"),
                        (result.ci_low, "confidence interval lower end"),
                        (result.ci_high, "confidence interval upper end")):
        if index is not None and index < len(result.roles):
            header = result.roles[index].header or f"column {index + 1}"
            parts.append(f"{name} is the column headed '{header}'")
    if result.combined:
        parts.append("each cell holds the estimate with its standard error in parentheses")
    if result.conventions.get("se_in_parens"):
        parts.append("the notes say standard errors are in parentheses")
    if result.stars_map:
        parts.append("the notes give a significance-star map")
    return "; ".join(parts)


def _should_skip(kind: str, has_estimate: bool) -> bool:
    """A descriptive table with no estimate inferred is not worth a model call."""
    from src.extraction.table_rules import DESCRIPTIVE

    return kind == DESCRIPTIVE and not has_estimate


def _drop_non_outcome_rows(raw: List[Any]):
    """Remove rows whose label is not an outcome (Observations, R2, Constant, Controls, ...)."""
    from src.extraction.table_rules import is_non_outcome_label

    kept, dropped = [], 0
    for row in raw:
        if isinstance(row, dict) and is_non_outcome_label(str(row.get("outcome") or "")):
            dropped += 1
        else:
            kept.append(row)
    return kept, dropped


async def extract_document(content_list: List[Dict[str, Any]], model: str, api_key: str) -> Dict[str, Any]:
    """All estimates in a document's tables, plus per-table decisions for auditing."""
    from src.extraction.dedupe import dedupe_estimates
    from src.extraction.table_rules import DESCRIPTIVE

    units = table_units(content_list)
    sem = asyncio.Semaphore(TABLE_CONCURRENCY)
    async with httpx.AsyncClient(timeout=300, headers={"Authorization": f"Bearer {api_key}"}) as client:
        async def one(u):
            kind, result, has_estimate = _table_analysis(u)
            if _should_skip(kind, has_estimate):
                return u, {"skipped": "descriptive table", "estimates": []}, None, kind
            structure = _structure_hint(result)
            prompt = PROMPT.format(context=(u["caption"] + "\n" + u["context"]).strip()[:4000] or "(none)",
                                   table=u["text"], page=u["page"] if u["page"] is not None else "?",
                                   structure=structure or "(none)")
            async with sem:
                for attempt in range(2):
                    try:
                        return u, _parse_json(await _chat(client, model, prompt)), None, kind
                    except Exception as e:
                        err = f"{type(e).__name__}: {e}"[:200]
                return u, {}, err, kind

        results = await asyncio.gather(*(one(u) for u in units))

    estimates, tables = [], []
    for u, data, err, kind in results:
        label = str(data.get("table_label") or u["caption"][:40] or f"table at item {u['index']}")
        is_results = bool(data.get("results_table"))
        raw = (data.get("estimates") or []) if is_results else []
        raw, non_outcome = _drop_non_outcome_rows(raw)
        rows = [to_estimate(r, label, u["page"], u["text"]) for r in raw if isinstance(r, dict)]
        estimates += rows
        tables.append({"table": label, "page": u["page"], "results_table": is_results, "estimates": len(rows),
                       "grounded": sum(r.grounded for r in rows), "error": err,
                       "skipped": data.get("skipped"),
                       "non_outcome_rows": non_outcome,
                       "review": kind == DESCRIPTIVE and is_results})
    estimate_dicts, duplicates = dedupe_estimates([asdict(e) for e in estimates])
    return {"estimates": estimate_dicts, "tables": tables, "duplicates": duplicates}
