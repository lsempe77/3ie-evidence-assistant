"""
3ie Evidence Assistant - Modal indexing writes chunks to the Supabase chunk store.

Runs embed_and_index locally with a fake Cohere client and a fake chunk store,
so no GPU, network or credentials are needed.
"""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infrastructure"))
modal_embedding = pytest.importorskip("modal_lib.embedding")

PROJECT = "11111111-2222-3333-4444-555555555555"


class FakeStore:
    def __init__(self):
        self.deleted = []
        self.upserts = []

    def delete_document(self, project_id, doc_key):
        self.deleted.append((project_id, doc_key))
        return 0

    def upsert_chunks(self, project_id, rows, batch_size=200):
        self.upserts.append((project_id, list(rows)))
        return len(rows)


@pytest.fixture
def fake_env(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(modal_embedding, "get_store", lambda: store)
    monkeypatch.setenv("COHERE_API_KEY", "test")
    monkeypatch.setenv("EMBEDDING_CACHE_ENABLED", "false")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class FakeCohere:
        def __init__(self, api_key):
            pass

        def embed(self, texts, model, input_type, embedding_types):
            floats = [[0.1, 0.2, 0.3] for _ in texts]
            return types.SimpleNamespace(embeddings=types.SimpleNamespace(float_=floats))

    monkeypatch.setitem(sys.modules, "cohere", types.SimpleNamespace(ClientV2=FakeCohere))
    return store


def test_embed_and_index_writes_rows_to_project(fake_env):
    content = " ".join(f"word{i}" for i in range(700))
    count = modal_embedding.embed_and_index(
        content=content,
        metadata={"title": "Study", "year": 2020, "authors": ["A"]},
        doc_id="ab12_study",
        project_id=PROJECT,
        enable_contextual=False,
    )
    assert count > 1
    assert fake_env.deleted == [(PROJECT, "ab12_study")]
    project, rows = fake_env.upserts[0]
    assert project == PROJECT and len(rows) == count
    first = rows[0]
    assert first["doc_key"] == "ab12_study" and first["chunk_index"] == 0
    assert first["content"] and first["embedding"] == [0.1, 0.2, 0.3]
    assert first["metadata"]["title"] == "Study" and first["metadata"]["year"] == 2020
    assert [r["chunk_index"] for r in rows] == list(range(count))


def test_legacy_collection_name_resolves_to_project(fake_env):
    modal_embedding.embed_and_index(
        content="short text " * 50, metadata={}, doc_id="d1",
        collection_name="rag_" + PROJECT.replace("-", ""), enable_contextual=False,
    )
    assert fake_env.upserts[0][0] == PROJECT


def test_tables_reach_the_chunks():
    """MinerU table items carry HTML in table_body and no text; they must still be chunked."""
    items = [
        {"type": "text", "text": "Introduction words " * 30, "page_idx": 0},
        {"type": "table", "table_caption": ["Table 2: Effects on income"],
         "table_body": "<table><tr><td>Income</td><td>0.25**</td></tr></table>", "page_idx": 4},
    ]
    chunks = modal_embedding.chunk_content_parent_child(items, child_size=50, parent_size=200, child_overlap=10)
    text = " ".join(c["text"] for c in chunks)
    assert "Table 2: Effects on income" in text and "0.25**" in text
    assert any(c["page_end"] == 5 for c in chunks)  # page numbers are 1-based in chunks


def test_docling_style_table_items_use_their_text():
    item = {"type": "table", "text": "Table 1. Package\n\n| Component | Months |", "page_idx": 2}
    assert modal_embedding.content_item_text(item).startswith("Table 1. Package")
