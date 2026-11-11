"""
Figures computed across a collection from its study facts (roadmap N6 step 3).

The answer model is given these lines next to the study findings, so questions about
typical costs, benefit-cost ratios, how many programmes and countries the evidence
covers, or whether programmes that put women first show different gains are answered
from numbers worked out here, in code, rather than by the model.

All figures are as reported by each study (currencies, price years and outcome
definitions differ), counted once per programme, and labelled as such. This is a
structured comparison of reported figures, not a meta-analysis.
"""

from __future__ import annotations

import re
from statistics import median
from typing import Any, Dict, List, Optional

WOMEN_FIRST = {"yes"}
NOT_WOMEN_FIRST = {"no", "mixed"}


def programme_key(facts: Dict[str, Any], doc_key: str) -> str:
    """
    One key per programme: the collection-level group when there is one
    (src/extraction/programme_groups.py), else the name without the country, lower case,
    punctuation removed.
    """
    name = facts.get("programme_group") or (facts.get("programme") or "").split(",")[0]
    name = re.sub(r"\(.*?\)", " ", name.lower())
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return name or f"doc:{doc_key}"


def _n(k: int, word: str = "programme") -> str:
    return f"{k} {word}{'' if k == 1 else 's'}"


def _money(x: float) -> str:
    return f"{x:,.0f}"


def _pct(x: float) -> str:
    return f"{x:+.0f}%"


def _ref(doc_keys: List[str], numbers: Dict[str, int]) -> str:
    cited = sorted({numbers[k] for k in doc_keys if k in numbers})
    return f" [{', '.join(map(str, cited[:3]))}]" if cited else ""


def _by_programme(facts_by_doc: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group evaluation documents by programme: {key: {"name", "docs", "facts": [...]}}."""
    out: Dict[str, Dict[str, Any]] = {}
    for doc_key, f in facts_by_doc.items():
        if not f.get("is_impact_evaluation"):
            continue  # reviews and overviews only relay other studies: never counted
        key = programme_key(f, doc_key)
        g = out.setdefault(key, {"name": f.get("programme_group") or f.get("programme") or doc_key[:40],
                                 "docs": [], "facts": []})
        g["docs"].append(doc_key)
        g["facts"].append(f)
    return out


def _women_flag(group: Dict[str, Any]) -> str:
    flags = {f.get("women_main_recipients") for f in group["facts"]} - {"not_stated", None}
    if flags & WOMEN_FIRST and not flags & NOT_WOMEN_FIRST:
        return "yes"
    if flags and not flags & WOMEN_FIRST:
        return "no"
    return "mixed" if flags else "not_stated"


def _dollars(item: Dict[str, Any]) -> Optional[str]:
    """'usd' for nominal US dollars, 'ppp' for PPP dollars, None for other currencies."""
    cur = item.get("currency", "").lower()
    if "ppp" in cur or "international" in cur:
        return "ppp"
    return "usd" if "usd" in cur or "$" in cur or "dollar" in cur else None


def summary_lines(facts_by_doc: Dict[str, Dict[str, Any]], numbers: Optional[Dict[str, int]] = None) -> List[str]:
    """
    The computed lines for the answer prompt. `numbers` maps doc keys to the citation
    numbers of the studies read for this question, so listed programmes can be cited.
    """
    numbers = numbers or {}
    groups = _by_programme(facts_by_doc)
    if not groups:
        return []
    lines: List[str] = []

    evaluations = [g for g in groups.values() if any(f.get("is_impact_evaluation") for f in g["facts"])]
    countries = sorted({c.strip() for g in evaluations for f in g["facts"] for c in f.get("countries") or [] if c.strip()})
    n_docs = sum(len(g["docs"]) for g in evaluations)
    lines.append(f"- Coverage: {n_docs} impact evaluations of about {len(evaluations)} distinct programmes in "
                 f"{len(countries)} countries ({', '.join(countries[:40])}).")
    women = {k: _women_flag(g) for k, g in groups.items()}
    n_women = sum(1 for k in women if women[k] == "yes" and groups[k] in evaluations)
    lines.append(f"- Women as the main recipients: {n_women} of the {len(evaluations)} programmes "
                 f"({sum(1 for k in women if women[k] == 'not_stated' and groups[k] in evaluations)} do not say).")

    # Cost per beneficiary, one figure per programme (the median of its documents' figures).
    # Nominal and PPP dollars are kept apart: PPP figures run two to three times higher.
    for kind, label in (("usd", "nominal US dollars"), ("ppp", "PPP dollars")):
        costs = []
        for k, g in groups.items():
            vals = [c["amount"] for f in g["facts"] for c in f.get("cost_per_beneficiary") or [] if _dollars(c) == kind]
            if vals:
                costs.append((median(vals), g))
        if not costs:
            continue
        values = sorted(v for v, _ in costs)
        listed = "; ".join(f"{g['name'][:45]} {_money(v)}{_ref(g['docs'], numbers)}"
                           for v, g in sorted(costs, key=lambda x: x[0]))
        lines.append(f"- Total cost per beneficiary in {label}, as reported by {_n(len(costs))} (price years and "
                     f"units, per household or per person, differ): median {_money(median(values))}, range "
                     f"{_money(values[0])} to {_money(values[-1])}. By programme: {listed}.")
    shares = []
    for k, g in groups.items():
        for kind in ("usd", "ppp"):
            cost = [c["amount"] for f in g["facts"] for c in f.get("cost_per_beneficiary") or [] if _dollars(c) == kind]
            transfer = [c["amount"] for f in g["facts"] for c in f.get("transfer_value") or [] if _dollars(c) == kind]
            if cost and transfer and median(transfer) < median(cost):
                shares.append(100 * median(transfer) / median(cost))
                break
    if len(shares) >= 2:
        lines.append(f"- Transfer value as a share of total cost, where both are reported ({_n(len(shares))}): "
                     f"median {median(shares):.0f}%, range {min(shares):.0f}% to {max(shares):.0f}%.")

    # Benefit-cost ratios
    ratios = []
    for k, g in groups.items():
        for f in g["facts"]:
            for b in f.get("benefit_cost") or []:
                ratios.append((b["ratio"], b.get("horizon_years"), g))
    if ratios:
        per_programme: Dict[str, float] = {}
        for r, _, g in ratios:
            per_programme.setdefault(g["name"], r)
        listed = "; ".join(f"{g['name'][:40]} {r:.2f}{f' over {h} years' if h else ''}{_ref(g['docs'], numbers)}"
                           for r, h, g in ratios[:14])
        lines.append(f"- Benefit-cost ratios reported by {_n(len(per_programme))}: median "
                     f"{median(per_programme.values()):.2f} (first figure per programme). Reported: {listed}.")

    # Headline effects as a percentage change, by whether women are the main recipients
    for outcome in ("income", "consumption", "assets", "savings", "poverty", "food_security"):
        by_flag: Dict[str, List[tuple]] = {"yes": [], "no": []}
        for k, g in groups.items():
            vals = [e["percent_change"] for f in g["facts"] for e in f.get("headline_effects") or []
                    if e.get("outcome") == outcome and e.get("percent_change") is not None]
            flag = "no" if women[k] in ("no", "mixed") else women[k]
            if vals and flag in by_flag:
                by_flag[flag].append((median(vals), g))
        total = len(by_flag["yes"]) + len(by_flag["no"])
        if total < 3:
            continue
        parts = []
        for flag, label in (("yes", "women as main recipients"), ("no", "other programmes")):
            items = by_flag[flag]
            if items:
                eg = ", ".join(f"{g['name'][:30]} {_pct(v)}{_ref(g['docs'], numbers)}" for v, g in sorted(items, key=lambda x: x[0])[:8])
                parts.append(f"{label}: median {_pct(median(v for v, _ in items))} across {_n(len(items))} ({eg})")
            else:
                parts.append(f"{label}: none report a percentage change")
        lines.append(f"- Headline {outcome.replace('_', ' ')} effects stated as a percentage change "
                     f"(one figure per programme, horizons differ): " + "; ".join(parts) + ".")
    return lines


def summary_block(facts_by_doc: Dict[str, Dict[str, Any]], numbers: Optional[Dict[str, int]] = None) -> str:
    lines = summary_lines(facts_by_doc, numbers)
    return "\n".join(lines) if lines else "(no study facts for this collection)"
