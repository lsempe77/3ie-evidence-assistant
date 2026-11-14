"""Deduplication of extracted estimates (src/extraction/dedupe.py)."""

from src.extraction.dedupe import dedupe_estimates


def row(outcome, arm="", subgroup="", effect=0.52, se=None, p=None, n=None, page=1):
    return {"outcome": outcome, "arm": arm, "subgroup": subgroup, "effect_size": effect,
            "standard_error": se, "t_stat": None, "ci_low": None, "ci_high": None,
            "p_value": p, "sample_size": n, "page": page}


def test_identical_rows_collapse():
    kept, dropped = dedupe_estimates([row("Consumption"), row("Consumption")])
    assert len(kept) == 1
    assert dropped == 1


def test_a_numbering_prefix_does_not_make_a_new_row():
    kept, dropped = dedupe_estimates([row("(1) Consumption"), row("Consumption"), row("Panel A: Consumption")])
    assert len(kept) == 1
    assert dropped == 2


def test_gaps_are_filled_from_a_later_duplicate():
    kept, _ = dedupe_estimates([row("Consumption", se=None), row("Consumption", se=0.12)])
    assert kept[0]["standard_error"] == 0.12


def test_distinct_arms_and_values_are_kept():
    kept, dropped = dedupe_estimates([row("Consumption", arm="T1"), row("Consumption", arm="T2"),
                                      row("Income", effect=0.9)])
    assert len(kept) == 3
    assert dropped == 0


def test_same_value_on_different_outcomes_is_not_merged():
    kept, _ = dedupe_estimates([row("Consumption"), row("Income")])
    assert len(kept) == 2


def test_two_different_standard_errors_are_not_merged():
    kept, dropped = dedupe_estimates([row("Consumption", se=0.10), row("Consumption", se=0.20)])
    assert len(kept) == 2
    assert dropped == 0
