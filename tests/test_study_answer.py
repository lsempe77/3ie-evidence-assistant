"""The /api/query study-synthesis path maps pipeline output to the frontend's shape."""

import asyncio

import pytest

from src.agents import study_synthesis as ss

api = pytest.importorskip("api.routes.api")


def reading(n, sid, relevant=True, design="rct", year=2015, score=0.6):
    return ss.StudyReading(
        number=n, study_id=sid, label=f"Author ({year}). Study {sid}", design=design, countries="Ghana",
        relevant=relevant, finding=f"Consumption rose in study {sid}." if relevant else "",
        direction="positive" if relevant else "not_applicable", quote=f"quote {sid}", page=12,
        best_score=score,
        metadata={"title": f"Study {sid}", "authors": ["A. Author", "B. Author"], "year": year,
                  "countries": ["Ghana"], "sectors": ["social protection"], "source": f"rags/p/{sid}.pdf"},
        passage=f"passage {sid}", passage_page=11,
    )


class FakePipeline:
    def __init__(self, project_id, reader_model, answer_model):
        FakePipeline.answer_model = answer_model

    async def run(self, question):
        readings = [reading(1, "s1"), reading(2, "s2", relevant=False), reading(3, "s3", design="difference_in_differences", year=2021, score=0.35)]
        # relevant studies are numbered [1] s1, [2] s3; the answer cites only [2]
        return ss.SynthesisResult(
            answer="Most studies found gains [2].",
            citations=[{"id": 2, "study_id": "s3", "title": "Study s3", "quote": "quote s3", "page": 12, "design": "did"}],
            readings=readings, model_used=FakePipeline.answer_model, timings={},
        )


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(ss, "StudySynthesisPipeline", FakePipeline)
    monkeypatch.setattr(api, "_generate_pdf_url", lambda study_id, source=None: f"https://pdf/{study_id}")
    return FakePipeline


def test_maps_relevant_studies_citations_and_counts(fake):
    resp = asyncio.run(api._answer_with_study_synthesis("Do programmes raise consumption?", "p", deep=False))
    assert resp.answer == "Most studies found gains [2]."
    assert [s.id for s in resp.studies] == ["s1", "s3"]          # irrelevant study left out
    assert [s.citationNumber for s in resp.studies] == [1, 2]
    assert resp.studies[0].finding == "Consumption rose in study s1."
    assert resp.studies[0].pdfUrl == "https://pdf/s1"
    assert resp.studies[1].confidence == "medium"
    assert [c.id for c in resp.citations] == [2] and resp.citations[0].studyId == "s3"
    assert resp.citations[0].page == 12
    assert resp.studiesRead == 3
    assert resp.evidenceHealth.studyCount == 2
    assert resp.evidenceHealth.dateRange == "2015 to 2021"
    assert resp.evidenceHealth.coverageWarning  # fewer than three studies


def test_deep_answer_uses_the_deep_model(fake, monkeypatch):
    monkeypatch.setattr(api.settings, "deep_answer_model", "deep/model")
    asyncio.run(api._answer_with_study_synthesis("q", "p", deep=True))
    assert fake.answer_model == "deep/model"
