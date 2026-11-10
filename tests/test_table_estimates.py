"""Number parsing and grounding for table estimate extraction (roadmap N6)."""

import pytest

from src.extraction.table_estimates import count_stars, parse_interval, parse_number, table_units, to_estimate


@pytest.mark.parametrize("text, value", [
    ("4,408", 4408.0),          # thousands separator (Burchi 2018, MWK)
    ("17,595***", 17595.0),
    ("1,234,567", 1234567.0),
    ("0,84", 0.84),             # decimal comma (Spanish tables)
    ("0,175", 0.175),           # leading zero: decimal, not 175
    ("1.234,5", 1234.5),
    ("-0.0577**", -0.0577),
    ("−0.18", -0.18),           # Unicode minus
    ("(1,369)", 1369.0),
    ("[0.12]", 0.12),
    ("633.63", 633.63),
    ("", None),
    ("n.s.", None),
])
def test_parse_number(text, value):
    assert parse_number(text) == value


def test_stars_and_intervals():
    assert count_stars("0.21***") == 3 and count_stars("0.21") == 0
    assert parse_interval("[0.05, 0.31]") == (0.05, 0.31)


TABLE = "| Outcome | Impact |\n|---|---|\n| Savings (MWK) | 4,408*** |\n|  | (1,369) |"


def test_grounded_estimate_parses_cells():
    e = to_estimate({"outcome": "Savings (MWK)", "estimate_cell": "4,408***", "se_cell": "(1,369)", "se_kind": "se"},
                    "Table 1", 11, TABLE)
    assert (e.effect_size, e.standard_error, e.stars, e.grounded) == (4408.0, 1369.0, 3, True)


def test_cell_not_in_table_is_not_grounded():
    e = to_estimate({"outcome": "Savings", "estimate_cell": "5,100***", "se_cell": ""}, "Table 1", 11, TABLE)
    assert e.grounded is False and e.notes


def test_table_units_carry_page_caption_and_context():
    items = [{"type": "text", "text": "Notes: standard errors in parentheses."},
             {"type": "table", "text": TABLE, "page_idx": "11", "table_caption": "['Table 1. Impacts']"},
             {"type": "text", "text": "*** p<0.01"}]
    (u,) = table_units(items)
    assert u["page"] == 11 and u["caption"] == "Table 1. Impacts" and "p<0.01" in u["context"]


def test_rows_for_keeps_grounded_numbers_and_cleans_values():
    from src.extraction.store_estimates import estimate_text, rows_for

    base = {"grounded": True, "effect_size": 0.2, "standard_error": float("inf"), "p_value": 3.0, "stars": 2,
            "sample_size": 1200.0, "ci_low": None, "ci_high": None, "table_label": "Table 2", "outcome": "Income\x00",
            "row_label": "Income", "column_label": "(1)", "arm": "", "subgroup": "Women", "estimate_cell": "0.20**",
            "se_cell": "(0.08)", "page": 7}
    out = {"estimates": [base, {**base, "grounded": False}, {**base, "effect_size": None}]}
    rows = rows_for("p", {"id": "d", "filename": "doc"}, out, "m")
    assert len(rows) == 1
    r = rows[0]
    assert r["standard_error"] is None and r["p_value"] is None and r["p_text"] == "**"
    assert r["sample_size"] == 1200 and isinstance(r["sample_size"], int)
    assert r["outcome_name"] == "Income" and r["treatment_arm"] is None
    assert r["literal_text"] == "0.20** (0.08)"
    assert estimate_text(r) == "Income | subgroup: Women"
