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
    pipe.project_id, pipe.store, pipe.use_study_cards, pipe._query_embeddings = "p", FakeStore(), True, {}
    pipe.use_estimates, pipe._estimate_tasks = False, {}
    passages, info = asyncio.run(pipe._candidates("question"))
    studies = [p.study_id for p in passages]
    # B had one pooled passage, C and D none: all three get their own passages
    assert pipe.store.asked_for == ["B", "C", "D"]
    assert {"A", "B", "C", "D"} == set(studies)
    assert studies.count("A") == ss.PASSAGES_PER_STUDY   # one long paper cannot crowd the others out
    assert info["studies_added_by_cards"] == 2


# --- extracted estimates in reading (roadmap N6) ---------------------------------

def test_significance_prefers_p_then_se_then_stars():
    assert ss.significance({"p_value": 0.03}) is True
    assert ss.significance({"effect_size": 4408, "standard_error": 1369}) is True     # t = 3.2
    assert ss.significance({"effect_size": 0.175, "standard_error": 0.19}) is False   # t = 0.9
    assert ss.significance({"effect_size": 0.59, "p_text": "***"}) is True
    assert ss.significance({"effect_size": 0.5, "p_text": "*"}) is None              # 10% at best
    assert ss.significance({"effect_size": 0.5}) is None


def test_reader_choices_resolve_only_listed_estimates():
    listed = [{"outcome_name": "Savings"}, {"outcome_name": "Consumption"}]
    assert ss._chosen(listed, ["E2", "e1", "E9", "x"]) == [listed[1], listed[0]]
    assert ss._chosen(listed, None) == []


def test_estimate_text_names_arm_size_significance_and_place():
    text = ss._estimate_text({"outcome_name": "Savings (MWK)", "treatment_arm": "Lump-sum only", "literal_text": "4,408*** (1,369)",
                              "effect_size": 4408.0, "standard_error": 1369.0, "table_number": "Table 1", "page": 11})
    assert text == "Savings (MWK) (Lump-sum only): 4,408*** (1,369) (significant at 5%; Table 1, p. 11)"


def test_study_response_carries_estimates(monkeypatch):
    """The API shape lists the estimates the reader used, with significance worked out."""
    from api.routes import api as routes
    from src.agents.study_synthesis import StudyReading

    monkeypatch.setattr(routes, "_generate_pdf_url", lambda *a: None)
    r = StudyReading(number=1, study_id="doc1", label="Banerjee 2015", design="rct", countries="Ghana",
                     relevant=True, finding="Consumption rose.", direction="positive", quote="q", page=3,
                     best_score=0.8, metadata={"title": "A study"},
                     estimates=[{"outcome_name": "Consumption", "treatment_arm": "Full package", "subgroup": None,
                                 "effect_size": 4408.0, "standard_error": 1369.0, "p_value": None, "p_text": "***",
                                 "literal_text": "4,408*** (1,369)", "sample_size": 2500, "table_number": "Table 3",
                                 "page": 14}])
    out = routes._study_response(r, 1)
    assert len(out.estimates) == 1
    e = out.estimates[0]
    assert e.value == "4,408*** (1,369)" and e.significant is True and e.table == "Table 3" and e.n == 2500
