"""/api/query/stream sends progress events, answer pieces and the full response (roadmap N2)."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agents import study_synthesis as ss

api = pytest.importorskip("api.routes.api")


def reading(n, sid, relevant=True):
    return ss.StudyReading(
        number=n, study_id=sid, label=f"A ({2015 + n}). Study {sid}", design="rct", countries="Ghana",
        relevant=relevant, finding=f"Savings rose in {sid}." if relevant else "", direction="positive",
        quote="q", page=3, best_score=0.6, metadata={"title": f"Study {sid}", "year": 2015 + n},
        passage="p", passage_page=3, programme="BRAC TUP, Bangladesh",
    )


class FakePipeline:
    async def suggest_followups(self, question, answer, readings):
        return ["Do the savings effects last?"]

    async def run_events(self, question):
        r1, r2 = reading(1, "s1"), reading(2, "s2", relevant=False)
        yield {"type": "stage", "stage": "searching"}
        yield {"type": "candidates", "total": 2}
        yield {"type": "study", "done": 1, "total": 2, "reading": r1}
        yield {"type": "study", "done": 2, "total": 2, "reading": r2}
        yield {"type": "stage", "stage": "writing"}
        yield {"type": "delta", "text": "Savings rose "}
        yield {"type": "delta", "text": "[1]."}
        yield {"type": "result", "result": ss.SynthesisResult(
            answer="Savings rose [1].", readings=[r1, r2], model_used="m",
            citations=[{"id": 1, "study_id": "s1", "title": "Study s1", "quote": "q", "page": 3, "design": "rct"}])}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "authorize_project", lambda ref, user: {"id": "p", "document_count": 97})
    monkeypatch.setattr(api, "_pipeline", lambda project_id, deep: FakePipeline())
    monkeypatch.setattr(api, "_generate_pdf_url", lambda study_id, source=None: None)

    class NoCache:
        async def get(self, **kw):
            return None

        async def set(self, **kw):
            return None

    monkeypatch.setattr(api, "get_response_cache", lambda: NoCache())
    app = FastAPI()
    app.include_router(api.router)  # the router carries its own /api prefix
    app.dependency_overrides[api.get_optional_user] = lambda: None
    return TestClient(app)


def parse(body: str):
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_stream_sends_progress_then_answer_then_done(client):
    r = client.post("/api/query/stream", json={"query": "Do programmes raise savings?", "collection": "p"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse(r.text)
    names = [e for e, _ in events]
    assert names[:3] == ["stage", "candidates", "stage"]
    assert events[0][1] == {"stage": "searching", "documents": 97}
    studies = [d for e, d in events if e == "study"]
    assert [s["relevant"] for s in studies] == [True, False]
    assert studies[0]["study"]["finding"] == "Savings rose in s1." and studies[1]["study"] is None
    assert "".join(d["text"] for e, d in events if e == "delta") == "Savings rose [1]."
    assert events[-1] == ("suggestions", {"questions": ["Do the savings effects last?"]})
    done = events[-2]
    assert done[0] == "done" and done[1]["answer"] == "Savings rose [1]." and done[1]["studiesRead"] == 2
    assert [s["id"] for s in done[1]["studies"]] == ["s1"]
