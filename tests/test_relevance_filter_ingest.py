"""The ingestion-side role filter (src/ingestion/relevance_filter.py), offline."""

import asyncio
import json

from src.ingestion import relevance_filter as rf

CONTENT = [
    {"type": "title", "text": "A study of cash transfers", "page_idx": 0},
    {"type": "text", "text": "We randomise 400 households.", "page_idx": 1},
    {"type": "text", "text": "Smith et al. (2010) found gains elsewhere.", "page_idx": 2},
    {"type": "text", "text": "References and acknowledgements.", "page_idx": 3},
]


def test_cached_labels_keep_only_own_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "load_content_list", lambda project_id, doc_key: CONTENT)
    (tmp_path / "p1__doc1.json").write_text(
        json.dumps(["abstract", "method", "other_study", "boilerplate"]), encoding="utf-8")

    units = asyncio.run(rf.filtered_units("p1", "doc1", "model", "key", cache_dir=tmp_path))

    assert [u["text"] for u in units] == [CONTENT[0]["text"], CONTENT[1]["text"]]


def test_a_failed_labelling_run_keeps_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "load_content_list", lambda project_id, doc_key: CONTENT)

    async def all_unlabelled(units, model, api_key):
        return ["unlabelled"] * len(units)

    monkeypatch.setattr(rf, "label_units", all_unlabelled)

    units = asyncio.run(rf.filtered_units("p1", "doc2", "model", "key", cache_dir=tmp_path))

    assert len(units) == len(CONTENT)


def test_labels_are_cached_after_one_run(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "load_content_list", lambda project_id, doc_key: CONTENT)
    calls = {"n": 0}

    async def once(units, model, api_key):
        calls["n"] += 1
        return ["abstract", "own_finding", "background", "boilerplate"]

    monkeypatch.setattr(rf, "label_units", once)

    asyncio.run(rf.filtered_units("p1", "doc3", "model", "key", cache_dir=tmp_path))
    asyncio.run(rf.filtered_units("p1", "doc3", "model", "key", cache_dir=tmp_path))

    assert calls["n"] == 1


def test_documents_carry_doc_key_and_page():
    docs = rf.documents_from_units([{"text": "some text", "page": 7, "kind": "text"}], "doc1")

    assert docs[0].text == "some text"
    assert docs[0].metadata["doc_id"] == "doc1"
    assert docs[0].metadata["page_start"] == 7


def test_chunking_keeps_each_units_page():
    # Regression: giving every unit Document the same `doc_id` argument made the chunker
    # collapse every page to the last one, which would break PDF highlighting.
    from src.ingestion.chunking import get_chunker

    units = [{"text": f"Paragraph {i} about results. " * 15, "page": i, "kind": "text"}
             for i in range(1, 21)]
    nodes = get_chunker("hybrid").chunk(rf.documents_from_units(units, "doc1"))

    assert {n.metadata.get("page_start") for n in nodes} == set(range(1, 21))
