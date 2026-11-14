"""
Interpret the structure of a parsed table: what each column means before its values are trusted.

Tables arrive as Markdown, one item per parsed table, so the same logical table can be split across
pages and the column meaning is carried by headers and notes that use inconsistent words. This module
recovers that structure deterministically:

- `parse_markdown_table` turns Markdown into header rows, body rows and non-table note lines.
- `parse_conventions` reads the notes ("standard errors in parentheses", "*** p<0.01", "95% CI").
- `infer_columns` assigns a role to each column from the header, the notes and the value profile, and
  uses arithmetic consistency (estimate / SE = t, estimate ± 1.96 SE = CI) to resolve the rest.
- `stitch_units` joins a table that continues on the next page into one grid.

Every role carries the evidence that produced it and every interpretation carries a confidence, so a
low-confidence table can be flagged for review instead of being silently trusted. This module only
interprets structure; it does not call a model or read values.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from src.extraction.table_estimates import parse_number

ESTIMATE = "estimate"
SE = "se"
T = "t"
P = "p"
CI_LOW = "ci_low"
CI_HIGH = "ci_high"
N = "n"
MEAN = "mean"
SD = "sd"
STARS = "stars"
UNKNOWN = "unknown"

# Two layouts cover most economics tables: statistics in columns (one column per statistic) and
# statistics in rows (one row per statistic, one column per outcome or model).
LAYOUT_COLUMNS = "roles_in_columns"
LAYOUT_ROWS = "roles_in_rows"

_HEADER_ROLES: List[Tuple[str, Tuple[str, ...]]] = [
    (ESTIMATE, ("coefficient", "coef", "estimate", "beta", "point estimate", "treatment effect",
                "att", "ate", "itt", "impact", "effect size", "marginal effect", "dy/dx",
                "odds ratio", "hazard ratio", "exp(b)",
                # Spanish, Portuguese, French
                "efecto", "impacto", "coeficiente", "estimacion", "efeito", "effet")),
    (CI_LOW, ("ci lower", "ci_low", "lower bound", "lower ci", "ll", "lb", "ci lb", "2.5%", "low",
              "confidence interval lower", "confidence interval low",
              "intervalo de confianza inferior", "limite inferior", "ic inferior",
              "intervalo de confianca inferior")),
    (CI_HIGH, ("ci upper", "ci_up", "upper bound", "upper ci", "ul", "ub", "ci ub", "97.5%", "high",
               "confidence interval upper", "confidence interval high",
               "intervalo de confianza superior", "limite superior", "ic superior",
               "intervalo de confianca superior")),
    (SE, ("std err", "std. err", "standard error", "robust se", "clustered se", "s.e.", "s.e", "se",
          "error estandar", "erro padrao", "erreur standard", "ee")),
    (T, ("t-stat", "t stat", "t statistic", "tstat", "z-stat", "z stat", "z statistic", "zscore",
         "z-score", "t value", "t-value", "z value", "estadistico t", "estatistica t", "statistique t")),
    (P, ("p-value", "p value", "pvalue", "pval", "prob", "significance level", "sig",
         "valor p", "p valor", "p-valor", "significancia", "probabilidad", "probabilidade", "probabilite")),
    (N, ("observations", "n obs", "num obs", "sample size", "number of observations", "clusters",
         "cluster", "n", "observaciones", "observacoes", "numero de observaciones")),
    (MEAN, ("control mean", "mean", "average", "avg", "baseline mean", "media", "promedio", "moyenne")),
    (SD, ("std dev", "std. dev", "standard deviation", "sigma", "sd",
          "desviacion estandar", "desvio padrao", "ecart type")),
]

_NOTES = {
    "se_in_parens": re.compile(r"(standard errors?|std\.? errs?|s\.?e\.?s?)[^.]{0,20}(\(|parenth)", re.I),
    "t_in_parens": re.compile(r"(t|z)[- ]?stat[^.]{0,40}(\(|parenth|bracket)", re.I),
    "ci": re.compile(r"(confidence interval|95%\s*ci|\bci\b)", re.I),
    "clustered": re.compile(r"cluster", re.I),
    "percent": re.compile(r"percent|%", re.I),
}
_STAR_NOTE = re.compile(r"(\*{1,3})\s*(?:for|:|=)?\s*(?:p\s*[<>=]?\s*)?0?\.(\d+)", re.I)
# "0.15*** (0.05)" or "[0.31] (0.10)": an estimate with stars and its standard error in one cell.
COMBINED_CELL = re.compile(
    r"^\s*[-−–]?\d[\d.,]*\s*(?:\*{1,3}|†{1,2})?\s*[(\[]\s*[-−–]?\d[\d.,]*\s*[)\]]\s*$"
)

# Header and label abbreviations expanded before matching, so "ATT" and "s.e." read as phrases.
_ABBREV = {
    "att": "treatment effect on the treated", "ate": "average treatment effect",
    "itt": "intention to treat effect", "tot": "treatment on the treated",
    "late": "local average treatment effect", "te": "treatment effect",
    "coef": "coefficient", "coeff": "coefficient", "coef.": "coefficient",
    "se": "standard error", "s.e.": "standard error", "std err": "standard error",
    "obs": "observations", "nobs": "observations", "n obs": "observations",
    "pval": "p value", "p-val": "p value", "sig": "significance",
    "pp": "percentage points", "sd": "standard deviation", "d": "effect size",
    "diff": "difference", "delta": "difference",
}


def expand_abbreviations(text: str) -> str:
    tokens = _norm(text).split()
    expanded = []
    for i, token in enumerate(tokens):
        pair = f"{tokens[i - 1]} {token}" if i else ""
        if pair in _ABBREV:
            expanded.append(_ABBREV[pair])
        elif token in _ABBREV:
            expanded.append(_ABBREV[token])
        else:
            expanded.append(token)
    return " ".join(expanded)


def _fold(text: object) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(text or "")) if not unicodedata.combining(c))


def _flat(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _norm(text: object) -> str:
    return re.sub(r"[^a-z0-9%./]+", " ", _fold(text).lower()).strip()


@dataclass
class TableGrid:
    headers: List[List[str]]
    body: List[List[str]]
    notes: List[str] = field(default_factory=list)

    @property
    def ncols(self) -> int:
        rows = self.headers + self.body
        return max((len(r) for r in rows), default=0)

    def column(self, index: int) -> List[str]:
        return [row[index] for row in self.body if index < len(row)]


@dataclass
class Column:
    index: int
    header: str
    role: str
    evidence: str
    profile: Dict[str, float] = field(default_factory=dict)


@dataclass
class Interpretation:
    roles: List[Column]
    estimate: Optional[int]
    se: Optional[int]
    t: Optional[int]
    p: Optional[int]
    ci_low: Optional[int]
    ci_high: Optional[int]
    combined: bool
    conventions: Dict[str, bool]
    stars_map: Dict[int, float]
    confidence: float
    warnings: List[str] = field(default_factory=list)
    layout: str = LAYOUT_COLUMNS
    row_roles: Dict[str, int] = field(default_factory=dict)


def _split_row(line: str) -> List[str]:
    cells = line.strip().strip("|").split("|")
    return [_flat(c) for c in cells]


def parse_markdown_table(text: str) -> TableGrid:
    """Header rows, body rows and note lines from a Markdown table."""
    rows: List[List[str]] = []
    separator_at: Optional[int] = None
    notes: List[str] = []
    for line in str(text or "").splitlines():
        if "|" in line:
            cells = _split_row(line)
            if re.fullmatch(r"[:\-\s|]+", line.strip()) and "-" in line:
                separator_at = len(rows) if separator_at is None else separator_at
                continue
            rows.append(cells)
        elif line.strip() and re.match(r"(note|notes|source|standard errors?|t-?stat|\*|†|cluster)", line.strip(), re.I):
            notes.append(_flat(line))
    if not rows:
        return TableGrid([], [], notes)
    if separator_at is not None:
        headers = rows[:separator_at] or rows[:1]
        body = rows[separator_at:]
    else:
        # No separator: the first row is the header unless it is mostly numeric.
        numeric = sum(1 for c in rows[0] if parse_number(c) is not None)
        headers = rows[:1] if numeric <= max(0, len(rows[0]) // 2) else []
        body = rows[len(headers):]
    return TableGrid(headers, body, notes)


def parse_conventions(notes: str) -> Tuple[Dict[str, bool], Dict[int, float]]:
    text = _flat(notes)
    conventions = {name: bool(pattern.search(text)) for name, pattern in _NOTES.items()}
    stars: Dict[int, float] = {}
    for stars_count, value in _STAR_NOTE.findall(text):
        stars[len(stars_count)] = float(f"0.{value}")
    return conventions, stars


def _role_from_header(header: str) -> Tuple[Optional[str], str]:
    key = expand_abbreviations(header)
    if not key:
        return None, ""
    for role, phrases in _HEADER_ROLES:
        for phrase in phrases:
            if len(phrase) <= 2:
                matched = key == phrase or re.search(rf"\b{re.escape(phrase)}\b", key)
            else:
                matched = key == phrase or key.startswith(phrase) or f" {phrase}" in f" {key}"
            if matched:
                return role, f"header '{_flat(header)}'"
    return None, ""


def _profile(values: Sequence[str]) -> Dict[str, float]:
    nums = [v for v in (parse_number(x) for x in values) if v is not None]
    if not nums:
        return {"n": 0.0}
    n = len(nums)
    return {
        "n": float(n),
        "min": min(nums),
        "max": max(nums),
        "share_unit_interval": sum(1 for v in nums if 0 <= v <= 1) / n,
        "share_integer": sum(1 for v in nums if float(v).is_integer()) / n,
        "share_small": sum(1 for v in nums if abs(v) <= 10) / n,
    }


def _profile_hint(profile: Dict[str, float]) -> Tuple[Optional[str], str]:
    n = profile.get("n", 0)
    if n < 3:
        return None, ""
    if profile["share_integer"] >= 0.9 and profile["min"] >= 20:
        return N, "value profile: whole counts"
    # A small decimal column could be a p-value, an SE, a coefficient or an elasticity, so the
    # value profile alone does not decide it. Leave it unknown for header, notes or arithmetic.
    return None, ""


def _combined_share(values: Sequence[str]) -> float:
    present = [v for v in values if str(v).strip()]
    if not present:
        return 0.0
    return sum(1 for v in present if COMBINED_CELL.match(str(v))) / len(present)


def infer_columns(grid: TableGrid, notes: str = "") -> List[Column]:
    conventions, _ = parse_conventions(notes)
    headers = [_flat(c) for c in (grid.headers[-1] if grid.headers else [])]
    columns: List[Column] = []
    for index in range(grid.ncols):
        header = headers[index] if index < len(headers) else ""
        role, evidence = _role_from_header(header)
        values = grid.column(index)
        if role is None and conventions["se_in_parens"] and _looks_like_estimate_column(values):
            role, evidence = SE, "notes: standard errors in parentheses"
        if role is None and _combined_share(values) >= 0.5:
            # Outcomes in columns, each cell "estimate*** (SE)" with no role labels at all. Half the
            # rows are enough, because one row may print "[p] estimate" instead of "estimate (SE)".
            role, evidence = ESTIMATE, "cells look like an estimate with its standard error"
        if role is None:
            hint, why = _profile_hint(_profile(values))
            if hint:
                role, evidence = hint, why
        columns.append(Column(index, header, role or UNKNOWN, evidence or "no evidence", _profile(values)))
    return columns


def _looks_like_estimate_column(values: Sequence[str]) -> bool:
    return any(re.search(r"[-−–]?\d[\d.,]*\s*(\(|\*+|†)", str(v)) for v in values)


def resolve_consistency(columns: List[Column], grid: TableGrid) -> Tuple[List[Column], List[str]]:
    """Resolve an unlabelled numeric column by arithmetic: estimate / SE = t and estimate ± 1.96 SE = CI."""
    warnings: List[str] = []
    estimate = next((c for c in columns if c.role == ESTIMATE), None)
    if estimate is None:
        return columns, warnings
    est_vals = [parse_number(x) for x in grid.column(estimate.index)]
    labelled = {c.role for c in columns if c.role != UNKNOWN}
    unknown = [c for c in columns if c.role == UNKNOWN and c.profile.get("n", 0) >= 2]
    has_t = T in labelled
    if unknown and not has_t:
        best, best_score = None, 0.0
        for cand in unknown:
            vals = [parse_number(x) for x in grid.column(cand.index)]
            pairs = [(e, v) for e, v in zip(est_vals, vals) if e not in (None, 0) and v not in (None, 0)]
            if not pairs:
                continue
            ratios = [abs(e / v) for e, v in pairs]
            consistent = sum(1 for r in ratios if 0.5 <= r <= 20 and abs(r - round(r)) < 0.05) / len(ratios)
            if consistent > best_score:
                best, best_score = cand, consistent
        if best is not None and best_score >= 0.5:
            best.role = SE
            best.evidence = f"consistency: estimate / column is a whole t-like ratio in {best_score:.0%} of rows"
            warnings.append("SE column has no header; inferred from arithmetic, check a sample")
    return columns, warnings


_PAREN_ONLY = re.compile(r"^\s*[(\[]\s*[-−–]?\d[\d.,]*\s*[)\]]\s*$")


def _all_parenthesised(cells: Sequence[str]) -> bool:
    present = [c for c in cells if str(c).strip()]
    return bool(present) and all(_PAREN_ONLY.match(str(c)) for c in present)


def _row_roles(grid: TableGrid) -> Dict[str, int]:
    """Roles carried by the first column, for the statistics-in-rows layout."""
    roles: Dict[str, int] = {}
    for i, row in enumerate(grid.body):
        label = row[0] if row else ""
        role, _ = _role_from_header(label)
        key = _norm(label)
        if role is None and key in ("treatment", "treat", "program", "programme", "impact", "effect"):
            role = ESTIMATE
        if role is None and ESTIMATE in roles and SE not in roles and _all_parenthesised(row[1:]):
            # The row under the coefficient row prints only "(SE)" in each outcome column.
            role = SE
        if role in (ESTIMATE, SE, T, P, N, CI_LOW, CI_HIGH) and role not in roles:
            roles[role] = i
    return roles


def interpret_table(text: str, notes: str = "") -> Interpretation:
    grid = parse_markdown_table(text)
    note_text = " ".join([notes] + grid.notes) if notes else " ".join(grid.notes)
    conventions, stars_map = parse_conventions(note_text)
    columns = infer_columns(grid, note_text)
    columns, warnings = resolve_consistency(columns, grid)
    row_roles = _row_roles(grid)
    layout = LAYOUT_ROWS if ESTIMATE in row_roles and len(row_roles) >= 2 else LAYOUT_COLUMNS

    def index_of(role: str) -> Optional[int]:
        return next((c.index for c in columns if c.role == role), None)

    estimate = index_of(ESTIMATE)
    if estimate is None:
        estimate = index_of(MEAN)
    combined = bool(estimate is not None and _looks_like_estimate_column(grid.column(estimate)))
    confidence = 0.4
    for col in columns:
        if col.role != UNKNOWN:
            confidence += 0.12
        if "consistency" in col.evidence:
            confidence += 0.15
    if conventions.get("se_in_parens") or conventions.get("ci"):
        confidence += 0.1
    if layout == LAYOUT_ROWS:
        confidence += 0.2
        warnings.append("statistics in rows: outcomes or models are columns, roles are rows")
    if estimate is None and layout == LAYOUT_COLUMNS:
        warnings.append("no estimate column identified")
    return Interpretation(
        roles=columns,
        estimate=estimate,
        se=index_of(SE),
        t=index_of(T),
        p=index_of(P),
        ci_low=index_of(CI_LOW),
        ci_high=index_of(CI_HIGH),
        combined=combined,
        conventions=conventions,
        stars_map=stars_map,
        confidence=min(0.95, confidence),
        warnings=warnings,
        layout=layout,
        row_roles=row_roles,
    )


def stitch_units(units: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """Merge a table continued on the next page into one unit.

    A unit is merged when it starts with the same header cells as the previous one (the header is
    repeated on the new page) or when its caption marks a continuation, and its page is at most one
    page after. The repeated header row is dropped and the bodies are concatenated.
    """
    merged: List[Dict[str, object]] = []
    for unit in units:
        if not merged:
            merged.append(dict(unit))
            continue
        prev = merged[-1]
        prev_grid = parse_markdown_table(str(prev.get("text") or ""))
        grid = parse_markdown_table(str(unit.get("text") or ""))
        same_header = bool(prev_grid.headers and grid.headers and prev_grid.headers[-1] == grid.headers[-1])
        caption = _flat(unit.get("caption")).lower()
        continued = "continued" in caption or "cont." in caption
        adjacent = (unit.get("page") is None or prev.get("page") is None
                    or int(unit["page"]) - int(prev["page"]) <= 1)
        if (same_header or continued) and adjacent:
            body = prev_grid.body + grid.body
            header = prev_grid.headers
            text = "\n".join("| " + " | ".join(r) + " |" for r in header + body)
            prev["text"] = text
            prev["page_end"] = unit.get("page")
            continue
        merged.append(dict(unit))
    return merged
