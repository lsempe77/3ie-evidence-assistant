"""
Table-structure coverage audit.

Runs the deterministic interpreter (`src/extraction/table_structure.py`) over every parsed table in the
collection and reports how often it recovers the structure: does it find an estimate column, a standard
error, a p-value, a confidence interval, a sample size; how confident is it; how many columns stay
unknown; and how often the table notes state the convention the values follow.

Read-only, no model calls. Uses the parsed content lists already cached by the usage study.

Usage:
    python evaluation/table_structure_audit.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
PROJ = "7efdc60e-e863-480c-929e-616574725e5f"
STUDY = ROOT / "evaluation" / "results" / "usage_study" / PROJ
REPORT = ROOT / "evaluation" / "results" / f"table_structure_audit_{date.today().isoformat()}.md"

import sys

sys.path.insert(0, str(ROOT))
from evaluation.usage_study import load_content  # noqa: E402
from src.extraction.table_estimates import table_units  # noqa: E402
from src.extraction.table_structure import (  # noqa: E402
    ESTIMATE, LAYOUT_ROWS, SE, UNKNOWN, interpret_table, parse_markdown_table, stitch_units,
)


def main() -> None:
    tables = 0
    estimate_tables = 0
    found = Counter()
    conditional = Counter()
    conventions = Counter()
    layouts = Counter()
    confidence: list = []
    unknown_share: list = []
    missed_headers: Counter = Counter()
    per_doc = Counter()

    for label_file in sorted((STUDY / "labels").glob("*.json")):
        doc_key = json.loads(label_file.read_text(encoding="utf-8"))["doc_key"]
        try:
            content = load_content(PROJ, doc_key, STUDY / "content")
        except Exception:
            continue
        units = stitch_units(table_units(content))
        per_doc[doc_key] = len(units)
        for unit in units:
            text = str(unit.get("text") or "")
            notes = f"{unit.get('caption') or ''} {unit.get('context') or ''}"
            result = interpret_table(text, notes=notes)
            tables += 1
            rows_layout = result.layout == LAYOUT_ROWS
            layouts["statistics in rows" if rows_layout else "statistics in columns"] += 1
            has_estimate = (ESTIMATE in result.row_roles) if rows_layout else (result.estimate is not None)
            if has_estimate:
                estimate_tables += 1
                found["estimate"] += 1
                se_present = (rows_layout and SE in result.row_roles) or result.se is not None or result.combined
                if se_present:
                    conditional["se"] += 1
                if (rows_layout and "p" in result.row_roles) or result.p is not None:
                    conditional["p"] += 1
                if (rows_layout and "ci_low" in result.row_roles) or (
                        result.ci_low is not None and result.ci_high is not None):
                    conditional["ci"] += 1
                if result.roles:
                    unknown_share.append(sum(1 for c in result.roles if c.role == UNKNOWN) / len(result.roles))
            elif result.conventions.get("se_in_parens") or result.stars_map:
                # A table whose notes state an SE convention or a star map is probably a results
                # table we failed to read, not a descriptive table. Record its header words.
                grid = parse_markdown_table(text)
                header = " | ".join(grid.headers[-1]) if grid.headers else "(no header)"
                missed_headers[header[:90]] += 1
            if result.se is not None:
                found["se"] += 1
            if result.p is not None:
                found["p"] += 1
            if result.ci_low is not None and result.ci_high is not None:
                found["ci"] += 1
            if result.combined:
                found["combined cell"] += 1
            if result.conventions.get("se_in_parens"):
                conventions["notes state SE in parentheses"] += 1
            if result.stars_map:
                conventions["notes state a star map"] += 1
            if result.conventions.get("ci"):
                conventions["notes mention a CI"] += 1
            confidence.append(result.confidence)

    def pct(n: int) -> str:
        return f"{n} ({100 * n / tables:.0f}%)" if tables else "0"

    def cpct(n: int) -> str:
        return f"{n} ({100 * n / estimate_tables:.0f}%)" if estimate_tables else "0"

    unknown_mean = 100 * mean(unknown_share) if unknown_share else 0.0

    lines = [
        "# Table-structure coverage audit",
        "",
        f"Tables parsed from {len(per_doc)} documents: {tables}. "
        f"Documents with at least one table: {sum(1 for v in per_doc.values() if v)}.",
        f"Tables with an estimate column or estimate row (results tables): {pct(estimate_tables)}. "
        "The rest are mostly descriptive tables (treatments, modules, sample sizes), which correctly "
        "have no estimate.",
        "",
        "| Layout | Tables |",
        "| --- | --- |",
    ]
    for name, count in layouts.most_common():
        lines.append(f"| {name} | {pct(count)} |")
    lines += [
        "",
        "## Coverage among results tables",
        "",
        "| Structure found | Of the tables with an estimate |",
        "| --- | --- |",
        f"| standard error (column or in the estimate cell) | {cpct(conditional['se'])} |",
        f"| p-value | {cpct(conditional['p'])} |",
        f"| confidence interval, both bounds | {cpct(conditional['ci'])} |",
        "",
        "| Structure found | All tables |",
        "| --- | --- |",
        f"| estimate column | {pct(found['estimate'])} |",
        f"| standard error column | {pct(found['se'])} |",
        f"| combined estimate and SE in one cell | {pct(found['combined cell'])} |",
        "",
        f"Mean confidence: {mean(confidence):.2f}." if confidence else "No tables.",
        f"Mean share of columns left unknown, on results tables: {unknown_mean:.0f}%.",
        "",
        "## Notes conventions",
        "",
        "| Notes convention | Tables |",
        "| --- | --- |",
    ]
    for name, count in conventions.most_common():
        lines.append(f"| {name} | {pct(count)} |")
    lines += ["", "## Header words on likely results tables that were not read (top 20)", ""]
    if missed_headers:
        lines += ["| Header row | Tables |", "| --- | --- |"]
        for header, count in missed_headers.most_common(20):
            lines.append(f"| `{header}` | {count} |")
    else:
        lines.append("None: every table with SE or star notes was read.")
    report = "\n".join(lines)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nwritten to {REPORT}")


if __name__ == "__main__":
    main()
