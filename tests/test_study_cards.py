"""Study cards and study-level candidate selection (roadmap N1), with fakes only."""

import asyncio

from src.agents import study_synthesis as ss
from src.retrieval.study_cards import card_text


def test_card_text_carries_what_decides_relevance():
    meta = {"title": "Targeting the Ultra Poor", "authors": ["A. Banerjee", "E. Duflo"], "year": 2017,
            "study_design": "cluster_rct", "countries": ["Bangladesh"], "sectors": ["social protection"],
            "intervention_type": "asset transfer and coaching"}
    text = card_text(meta, "Abstract. We study a graduation programme in rural Bangladesh.")
    assert text.startswith("Targeting the Ultra Poor\n")
    for part in ("Design: cluster_rct", "Countries: Bangladesh", "Intervention: asset transfer and coaching",
                 "We study a graduation programme"):
        assert part in text


def test_card_text_prefers_a_real_abstract_and_skips_unknown_design():
    meta = {"title": "T", "study_design": "unknown", "abstract": "A" * 300}
    text = card_text(meta, "opening text")
    assert "Design:" not in text and "opening text" not in text and "A" * 300 in text


def row(i, doc, score=0.5):
    return {"id": f"c{i}", "doc_key": doc, "chunk_index": i, "content": f"text {i}", "metadata": {"doc_id": doc},
            "score": score, "page_start": i}


class FakeStore:
    def __init__(self):
        self.asked_for = None

    def hybrid_search(self, project_id, question, emb, match_count, candidate_count):
        # The passage pool is dominated by study A
        return [row(i, "A") for i in range(6)] + [row(10, "B")]

    def search_study_cards(self, project_id, question, emb, match_count):
        return [{"doc_key": d} for d in ("A", "B", "C", "D")]

    def passages_for_studies(self, project_id, emb, doc_keys, per_doc):
        self.asked_for = list(doc_keys)
        return [row(20 + n, d) for n, d in enumerate(doc_keys)]


def test_candidates_add_studies_the_pool_missed(monkeypatch):
    monkeypatch.setattr(ss, "embed_query", lambda q: [0.1, 0.2])
    pipe = ss.StudySynthesisPipeline.__new__(ss.StudySynthesisPipeline)
    pipe.project_id, pipe.store, pipe.use_study_cards = "p", FakeStore(), True
    passages, info = asyncio.run(pipe._candidates("question"))
    studies = [p.study_id for p in passages]
    # B had one pooled passage, C and D none: all three get their own passages
    assert pipe.store.asked_for == ["B", "C", "D"]
    assert {"A", "B", "C", "D"} == set(studies)
    assert studies.count("A") == ss.PASSAGES_PER_STUDY   # one long paper cannot crowd the others out
    assert info["studies_added_by_cards"] == 2
