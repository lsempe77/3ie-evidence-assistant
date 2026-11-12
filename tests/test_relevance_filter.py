"""The role filter that decides what reaches the index (src/extraction/relevance_labels.py)."""

from src.extraction.relevance_labels import KEEP, filter_units, keep_results_tables


def _unit(kind: str, text: str, page: int = 1):
    return {"index": 0, "kind": kind, "page": page, "text": text}


def test_keeps_evidence_roles_and_drops_noise_in_order():
    units = [
        _unit("text", "This study randomises 400 households."),
        _unit("text", "Earlier work by Banerjee et al. (2015) found gains."),
        _unit("table", "Treatment  Control  Difference\n12.3  9.8  2.5"),
        _unit("text", "Acknowledgements and references follow."),
    ]
    labels = ["method", "other_study", "own_finding", "boilerplate"]

    kept = filter_units(units, labels)

    assert [u["text"] for u in kept] == [units[0]["text"], units[2]["text"]]
    assert kept[0] is units[0]  # verbatim, not rewritten


def test_promotes_a_results_table_labelled_boilerplate():
    units = [_unit("table", "Table 3: Effects of the programme on consumption")]
    labels = ["boilerplate"]

    kept = filter_units(units, labels)

    assert len(kept) == 1
    assert kept[0]["text"].startswith("Table 3")


def test_promotes_a_table_whose_estimates_were_extracted():
    units = [_unit("table", "Numbers only")]
    labels = ["boilerplate"]

    assert keep_results_tables(units, labels, {0}) == ["own_finding"]
    assert len(filter_units(units, labels, {0})) == 1


def test_drops_unlabelled_paragraphs():
    units = [_unit("text", "Some text the model did not label")]

    assert filter_units(units, ["unlabelled"]) == []


def test_keep_set_matches_the_study_roles():
    assert KEEP == {"abstract", "own_finding", "method", "intervention", "setting", "cost", "limitation"}
