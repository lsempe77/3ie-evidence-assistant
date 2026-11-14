"""Table-type and non-outcome rules, ported from TVET (src/extraction/table_rules.py)."""

from src.extraction.table_rules import (
    DESCRIPTIVE, RESULTS, UNKNOWN,
    classify_table, is_descriptive_column, is_non_outcome_label,
)


def test_balance_and_summary_tables_are_descriptive():
    assert classify_table("Table 1: Balance table, baseline characteristics")[0] == DESCRIPTIVE
    assert classify_table("Summary statistics of the sample")[0] == DESCRIPTIVE
    assert classify_table("Attrition and sample characteristics")[0] == DESCRIPTIVE
    assert classify_table("Table 3. Propensity score matching, covariates")[0] == DESCRIPTIVE


def test_a_matching_results_table_is_results_not_balance():
    assert classify_table("Table 1. Double-difference propensity score matching results")[0] == RESULTS


def test_impact_and_regression_tables_are_results():
    assert classify_table("Table 4: Impacts of the programme on consumption")[0] == RESULTS
    assert classify_table("Table 2. Regression results, treatment effect")[0] == RESULTS
    assert classify_table("Estimation results: ITT and ATT")[0] == RESULTS


def test_a_descriptive_cue_wins_over_a_results_cue():
    kind, reason = classify_table("Baseline characteristics and impacts")
    assert kind == DESCRIPTIVE
    assert "baseline" in reason


def test_missing_context_is_unknown():
    assert classify_table("")[0] == UNKNOWN


def test_non_outcome_row_labels():
    for label in ("Observations", "Number of observations", "R-squared", "Adjusted R2",
                  "Constant", "Controls", "Fixed effects", "F-statistic", "N", "SD", "Clusters"):
        assert is_non_outcome_label(label), label
    for label in ("Total consumption", "Age of household head", "Probability of employment",
                  "Average effect of T1", "Mean impact on consumption"):
        assert not is_non_outcome_label(label), label


def test_descriptive_columns():
    assert is_descriptive_column("Control mean")
    assert is_descriptive_column("Standard deviation")
    assert is_descriptive_column("SD")
    assert not is_descriptive_column("Coefficient")
    assert not is_descriptive_column("Standard error")
