"""Integration of table typing and structure into the table reader (src/extraction/table_estimates.py)."""

from src.extraction.table_estimates import (
    _drop_non_outcome_rows, _should_skip, _structure_hint, _table_analysis,
)

RESULTS = "| Outcome | Coefficient | Standard error |\n| --- | --- | --- |\n| Food | 0.52 | 0.12 |"
ATTRITION = "| Region | Attrition rate |\n| --- | --- |\n| North | 0.12 |\n| South | 0.09 |"


def unit(text, caption=""):
    return {"index": 0, "page": 5, "caption": caption, "context": "", "text": text}


def test_a_descriptive_table_without_an_estimate_is_skipped():
    kind, _, has_estimate = _table_analysis(unit(ATTRITION, "Table 3. Attrition by region"))
    assert kind == "descriptive"
    assert has_estimate is False
    assert _should_skip(kind, has_estimate) is True


def test_a_results_table_is_not_skipped():
    kind, _, has_estimate = _table_analysis(unit(RESULTS, "Table 4. Impacts on consumption"))
    assert kind == "results"
    assert has_estimate is True
    assert _should_skip(kind, has_estimate) is False


def test_the_structure_hint_names_the_columns():
    _, result, _ = _table_analysis(unit(RESULTS))
    hint = _structure_hint(result)
    assert "estimate is the column headed 'Coefficient'" in hint
    assert "standard error is the column headed 'Standard error'" in hint


def test_non_outcome_rows_are_dropped_and_real_effects_kept():
    raw = [{"outcome": "Food consumption"}, {"outcome": "Observations"},
           {"outcome": "Constant"}, {"outcome": "Average effect of T1"}]
    kept, dropped = _drop_non_outcome_rows(raw)
    assert [r["outcome"] for r in kept] == ["Food consumption", "Average effect of T1"]
    assert dropped == 2
