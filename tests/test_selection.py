"""Tests for choosing passages by study, and for metadata reaching citations."""

from dataclasses import dataclass, field
from typing import Any, Dict

from src.retrieval.context_builder import ContextBuilder, _joined
from src.retrieval.hybrid_retriever import RetrievalResult
from src.retrieval.selection import select_by_study


@dataclass
class P:
    study_id: str
    score: float
    meta: Dict[str, Any] = field(default_factory=dict)


def ids(rows):
    return [(r.study_id, r.score) for r in rows]


class TestSelectByStudy:
    def test_one_long_paper_cannot_fill_every_slot(self):
        # Ten passages from study A outrank everything else. The old top-N cut
        # returned only A; selection by study keeps A's best three, then B and C.
        rows = [P("A", 0.9 - i * 0.01) for i in range(10)] + [P("B", 0.6), P("C", 0.5)]
        out = select_by_study(rows, max_studies=3, passages_per_study=3)
        assert [r.study_id for r in out].count("A") == 3
        assert {r.study_id for r in out} == {"A", "B", "C"}

    def test_study_cap_and_best_first_order(self):
        rows = [P("A", 0.9), P("B", 0.8), P("A", 0.7), P("C", 0.6), P("D", 0.5)]
        out = select_by_study(rows, max_studies=2)
        assert ids(out) == [("A", 0.9), ("B", 0.8), ("A", 0.7)]

    def test_min_score_drops_weak_passages_first(self):
        rows = [P("A", 0.6), P("B", 0.15), P("C", 0.3)]
        out = select_by_study(rows, max_studies=10, min_score=0.2)
        assert {r.study_id for r in out} == {"A", "C"}

    def test_everything_below_floor_returns_empty(self):
        assert select_by_study([P("A", 0.1)], max_studies=5, min_score=0.2) == []

    def test_no_limits_means_nothing(self):
        assert select_by_study([P("A", 0.9)], max_studies=0) == []


class TestMetadataReachesCitations:
    def test_joined_prefers_plural_list_keys(self):
        assert _joined({"countries": ["Bangladesh", "India"]}, "countries", "country") == "Bangladesh, India"
        assert _joined({"country": "Peru"}, "countries", "country") == "Peru"
        assert _joined({"countries": []}, "countries", "country") == ""

    def test_citations_carry_country_sector_and_design(self, monkeypatch):
        monkeypatch.setattr("src.retrieval.context_builder.TRUST_COUNTRY_METADATA", True)
        result = RetrievalResult(
            node_id="n1",
            text="Consumption rose by 0.12 standard deviations.",
            score=0.6,
            metadata={
                "doc_id": "tup", "title": "Targeting the ultra poor", "year": 2017,
                "countries": ["Bangladesh"], "sectors": ["social protection"],
                "study_design": "cluster_rct", "study_design_confidence": 0.9,
                "page_start": 12, "page_end": 12,
            },
        )
        grouped = ContextBuilder().build([result]).citations
        _, flat = ContextBuilder()._build_flat_context([result])
        for c in (grouped[0], flat[0]):
            assert c["country"] == "Bangladesh"
            assert c["sector"] == "social protection"
            assert c["study_design"] == "cluster_rct"

    def test_untrusted_countries_are_withheld(self, monkeypatch):
        monkeypatch.setattr("src.retrieval.context_builder.TRUST_COUNTRY_METADATA", False)
        result = RetrievalResult(node_id="n1", text="x", score=0.6,
                                 metadata={"doc_id": "d", "title": "T", "countries": ["US"]})
        assert ContextBuilder().build([result]).citations[0]["country"] == ""
