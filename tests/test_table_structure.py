"""Table structure interpretation: roles, notes, consistency, and multi-page stitching."""

from src.extraction.table_structure import (
    ESTIMATE, LAYOUT_ROWS, SE,
    interpret_table, parse_conventions, parse_markdown_table, stitch_units,
)

TABLE_SE = """| Coefficient | SE | p-value |
| --- | --- | --- |
| 0.52 | 0.12 | 0.001 |
| 0.31 | 0.10 | 0.010 |"""

TABLE_CI = """| Coef | 95% CI lower | 95% CI upper |
| --- | --- | --- |
| 0.52 | 0.29 | 0.75 |
| 0.31 | 0.11 | 0.51 |"""


def test_header_roles_for_a_plain_results_table():
    result = interpret_table(TABLE_SE)
    assert result.estimate == 0
    assert result.se == 1
    assert result.p == 2
    assert result.confidence >= 0.6


def test_statistics_in_rows_with_outcomes_in_columns():
    table = """| | (1) | (2) |
| --- | --- | --- |
| Coefficient | 0.52 | 0.31 |
| Standard error | 0.12 | 0.10 |
| Observations | 400 | 400 |"""
    result = interpret_table(table)
    assert result.layout == LAYOUT_ROWS
    assert result.row_roles.get(ESTIMATE) == 0
    assert result.row_roles.get(SE) == 1


def test_spanish_headers_are_read():
    table = """| Efecto | Error estándar | Valor p |
| --- | --- | --- |
| 0.52 | 0.12 | 0.001 |"""
    result = interpret_table(table)
    assert result.estimate == 0
    assert result.se == 1
    assert result.p == 2


def test_header_abbreviations_are_expanded():
    table = """| ATT | s.e. | Obs |
| --- | --- | --- |
| 0.52 | 0.12 | 400 |
| 0.41 | 0.10 | 400 |"""
    result = interpret_table(table)
    assert result.estimate == 0
    assert result.se == 1
    assert any(c.role == "n" for c in result.roles)


def test_confidence_interval_columns():
    result = interpret_table(TABLE_CI)
    assert result.estimate == 0
    assert result.ci_low == 1
    assert result.ci_high == 2


def test_notes_set_the_conventions_and_star_map():
    conventions, stars = parse_conventions(
        "Standard errors in parentheses. *** p<0.01, ** p<0.05, * p<0.1. Clustered at village level.")
    assert conventions["se_in_parens"] and conventions["clustered"]
    assert stars == {3: 0.01, 2: 0.05, 1: 0.1}


def test_combined_estimate_and_se_cell_is_flagged():
    table = """| Estimate |
| --- |
| 0.52*** (0.12) |
| 0.31** (0.10) |"""
    result = interpret_table(table, notes="Standard errors in parentheses")
    assert result.estimate == 0
    assert result.combined is True


def test_consistency_finds_an_unlabelled_se_column():
    table = """| Coef | A | B |
| --- | --- | --- |
| 0.50 | 0.10 | 5.00 |
| 0.60 | 0.20 | 3.00 |
| 0.40 | 0.05 | 8.00 |"""
    result = interpret_table(table)
    roles = {c.index: c.role for c in result.roles}
    assert roles[0] == ESTIMATE
    assert roles[1] == SE  # estimate / 0.1 is a whole ratio, estimate / 5 is not


def test_unknown_table_warns_rather_than_guessing():
    table = """| Region | Note |
| --- | --- |
| North | high |
| South | low |"""
    result = interpret_table(table)
    assert result.estimate is None
    assert any("no estimate" in w for w in result.warnings)


def test_separator_rows_are_not_body_rows():
    grid = parse_markdown_table(TABLE_SE)
    assert len(grid.body) == 2
    assert grid.headers[-1][0].lower().startswith("coefficient")


def test_continuation_on_the_next_page_is_stitched():
    units = [
        {"page": 3, "caption": "Table 4. Impacts on consumption",
         "text": "| Outcome | Coef | SE |\n| --- | --- | --- |\n| Food | 0.52 | 0.12 |"},
        {"page": 4, "caption": "Table 4. Impacts on consumption (continued)",
         "text": "| Outcome | Coef | SE |\n| --- | --- | --- |\n| Assets | 0.31 | 0.10 |"},
    ]
    merged = stitch_units(units)
    assert len(merged) == 1
    assert merged[0]["page"] == 3
    assert merged[0]["page_end"] == 4
    assert "Food" in merged[0]["text"] and "Assets" in merged[0]["text"]


def test_a_new_table_on_the_next_page_is_not_stitched():
    units = [
        {"page": 3, "caption": "Table 4", "text": "| A | B |\n| --- | --- |\n| 1 | 2 |"},
        {"page": 4, "caption": "Table 5", "text": "| X | Y |\n| --- | --- |\n| 3 | 4 |"},
    ]
    assert len(stitch_units(units)) == 2
