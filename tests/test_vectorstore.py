"""
3ie Evidence Assistant - Tests for the Supabase chunk store, retriever and indexer.

The Supabase REST API is replaced by an in-memory httpx MockTransport, so these
tests need no network and no credentials.
"""

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import httpx
import pytest

from src.ingestion.indexer import ChunkIndexer, doc_key_from
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.query_processor import ExtractedFilters
from src.vectorstore import ChunkStore, legacy_collection_to_project_id, to_chunk_row

PROJECT = "11111111-2222-3333-4444-555555555555"


class FakeSupabase:
    """Records requests and answers the handful of endpoints ChunkStore uses."""

    def __init__(self):
        self.requests: List[httpx.Request] = []
        self.search_rows: List[Dict[str, Any]] = []
        self.delete_count = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/rpc/hybrid_search"):
            return httpx.Response(200, json=self.search_rows)
        if path.endswith("/rpc/project_chunk_stats"):
            return httpx.Response(200, json=[{"chunk_count": 7, "document_count": 2, "embedded_count": 7}])
        if path.endswith("/rpc/merge_chunk_metadata"):
            return httpx.Response(200, json=3)
        if path.endswith("/chunks") and request.method == "POST":
            return httpx.Response(201)
        if path.endswith("/chunks") and request.method == "DELETE":
            return httpx.Response(204, headers={"content-range": f"*/{self.delete_count}"})
        if path.endswith("/chunks") and request.method == "GET":
            return httpx.Response(200, json=[], headers={"content-range": "*/42"})
        return httpx.Response(404, json={"message": "not mocked"})

    def store(self) -> ChunkStore:
        return ChunkStore(url="https://example.supabase.co", secret_key="sb_secret_test",
                          transport=httpx.MockTransport(self.handler))


def _row(i: int, score: float, embedding=None, **meta) -> Dict[str, Any]:
    return {
        "id": f"00000000-0000-0000-0000-00000000000{i}", "doc_key": "doc1", "chunk_index": i,
        "content": f"chunk {i}", "context_prefix": "From a study", "parent_text": f"parent {i}",
        "page_start": i + 1, "page_end": i + 1, "section": None,
        "metadata": {"title": "Study", "year": 2020, **meta},
        "semantic_rank": i + 1, "keyword_rank": None, "semantic_distance": 0.1 * i,
        "score": score, "embedding": json.dumps(embedding) if embedding else None,
    }


class FakeEmbedder:
    def __init__(self, vector=(1.0, 0.0, 0.0)):
        self.vector = list(vector)

    def embed_query(self, query: str) -> List[float]:
        return self.vector


# --------------------------------------------------------------------- helpers

class TestHelpers:
    def test_legacy_collection_maps_to_uuid(self):
        assert legacy_collection_to_project_id("rag_" + PROJECT.replace("-", "")) == PROJECT

    def test_plain_uuid_passes_through(self):
        assert legacy_collection_to_project_id(PROJECT.upper()) == PROJECT

    def test_legacy_collection_rejects_other_names(self):
        assert legacy_collection_to_project_id("devchat_v2_contextual") is None
        assert legacy_collection_to_project_id(None) is None

    def test_to_chunk_row_moves_unknown_keys_into_metadata(self):
        row = to_chunk_row(PROJECT, {"doc_key": "d", "chunk_index": 0, "content": "x",
                                     "title": "T", "metadata": {"year": 2020}})
        assert row["rag_project_id"] == PROJECT
        assert row["metadata"] == {"year": 2020, "title": "T"}
        assert "title" not in row

    def test_to_chunk_row_requires_identity(self):
        with pytest.raises(ValueError):
            to_chunk_row(PROJECT, {"content": "x"})

    @pytest.mark.parametrize("value", ["input-pdfs/ab12_file.pdf", "ab12_file.pdf", "ab12_file", "a\\b\\ab12_file.pdf"])
    def test_doc_key_from(self, value):
        assert doc_key_from(value) == "ab12_file"


# ----------------------------------------------------------------- chunk store

class TestChunkStore:
    def test_upsert_batches_and_uses_conflict_key(self):
        fake = FakeSupabase()
        rows = [{"doc_key": "d", "chunk_index": i, "content": "x", "embedding": [0.1]} for i in range(5)]
        assert fake.store().upsert_chunks(PROJECT, rows, batch_size=2) == 5
        posts = [r for r in fake.requests if r.method == "POST"]
        assert len(posts) == 3
        assert posts[0].url.params["on_conflict"] == "rag_project_id,doc_key,chunk_index"
        assert "resolution=merge-duplicates" in posts[0].headers["prefer"]

    def test_hybrid_search_sends_filters_and_parses_embeddings(self):
        fake = FakeSupabase()
        fake.search_rows = [_row(0, 0.03, embedding=[1, 0, 0])]
        rows = fake.store().hybrid_search(PROJECT, "q", [0.5, 0.5], match_count=5,
                                          year_min=2015, sectors=["health"], with_embeddings=True)
        body = json.loads(fake.requests[-1].content)
        assert body["p_project_id"] == PROJECT and body["year_min"] == 2015 and body["sectors"] == ["health"]
        assert "year_max" not in body  # unset filters are omitted
        assert json.loads(body["query_embedding"]) == [0.5, 0.5]
        assert rows[0]["embedding"] == [1.0, 0.0, 0.0]

    def test_delete_and_count_read_content_range(self):
        fake = FakeSupabase()
        fake.delete_count = 12
        store = fake.store()
        assert store.delete_document(PROJECT, "doc1") == 12
        assert store.count(PROJECT) == 42

    def test_stats_and_merge_metadata(self):
        store = FakeSupabase().store()
        assert store.stats(PROJECT) == {"chunk_count": 7, "document_count": 2, "embedded_count": 7}
        assert store.merge_metadata(PROJECT, "doc1", {"title": "T"}) == 3

    def test_errors_raise(self):
        def fail(request):
            return httpx.Response(500, text="boom")
        store = ChunkStore(url="https://x.supabase.co", secret_key="k", transport=httpx.MockTransport(fail))
        with pytest.raises(Exception, match="boom"):
            store.stats(PROJECT)


# ------------------------------------------------------------------- retriever

class TestHybridRetriever:
    def _retriever(self, fake, mmr=False, query_vector=(1.0, 0.0, 0.0)):
        return HybridRetriever(project_id=PROJECT, store=fake.store(),
                               embedding_generator=FakeEmbedder(query_vector), mmr_enabled=mmr)

    @pytest.mark.asyncio
    async def test_results_keep_legacy_metadata_keys(self):
        fake = FakeSupabase()
        fake.search_rows = [_row(0, 0.03), _row(1, 0.02)]
        results = await self._retriever(fake).retrieve("q", top_k=2)
        assert [r.text for r in results] == ["chunk 0", "chunk 1"]
        first = results[0]
        assert first.parent_text == "parent 0"
        assert first.metadata["doc_id"] == "doc1"
        assert first.metadata["page_start"] == 1
        assert first.metadata["contextual_prefix"] == "From a study"
        assert first.study_id == "doc1" and first.year == 2020

    @pytest.mark.asyncio
    async def test_filters_and_keyword_switch(self, monkeypatch):
        fake = FakeSupabase()
        await self._retriever(fake).retrieve("q", top_k=3, filters=ExtractedFilters(year_min=2018), alpha=0.5)
        body = json.loads(fake.requests[-1].content)
        assert body["year_min"] == 2018
        assert body["full_text_weight"] == 1.0
        await self._retriever(fake).retrieve("q", top_k=3, alpha=1.0)
        assert json.loads(fake.requests[-1].content)["full_text_weight"] == 0.0

    @pytest.mark.asyncio
    async def test_mmr_uses_returned_embeddings(self):
        fake = FakeSupabase()
        # Query sits between two directions. Chunks 0 and 1 are near-duplicates; chunk 2 is
        # equally relevant but distinct, so MMR keeps one of the duplicates plus chunk 2.
        fake.search_rows = [_row(0, 0.05, [1, 0, 0]), _row(1, 0.04, [0.99, 0.01, 0]), _row(2, 0.03, [0, 1, 0])]
        results = await self._retriever(fake, mmr=True, query_vector=(1.0, 1.0, 0.0)).retrieve("q", top_k=2)
        assert json.loads(fake.requests[-1].content)["with_embeddings"] is True
        assert [r.text for r in results] == ["chunk 1", "chunk 2"]

    def test_legacy_collection_name_accepted(self):
        fake = FakeSupabase()
        r = HybridRetriever(collection_name="rag_" + PROJECT.replace("-", ""), store=fake.store(),
                            embedding_generator=FakeEmbedder())
        assert r.project_id == PROJECT

    def test_requires_project(self):
        with pytest.raises(ValueError):
            HybridRetriever(store=FakeSupabase().store(), embedding_generator=FakeEmbedder())


# --------------------------------------------------------------------- indexer

class TestChunkIndexer:
    def test_node_to_row(self):
        node = SimpleNamespace(
            node_id="n1", embedding=[0.1, 0.2],
            metadata={"doc_id": "ab12_file", "chunk_index": 3, "page_start": 4, "page_end": 5,
                      "parent_text": "P", "contextual_prefix": "C", "title": "T"},
            get_content=lambda: "body",
        )
        row = ChunkIndexer.node_to_row(node)
        assert (row["doc_key"], row["chunk_index"], row["content"]) == ("ab12_file", 3, "body")
        assert (row["parent_text"], row["context_prefix"], row["page_start"]) == ("P", "C", 4)
        assert row["metadata"]["title"] == "T" and "parent_text" not in row["metadata"]

    def test_index_nodes_writes_rows(self):
        fake = FakeSupabase()
        node = SimpleNamespace(node_id="n1", embedding=[0.1], metadata={"doc_id": "d"}, get_content=lambda: "x")
        indexer = ChunkIndexer(project_id=PROJECT, store=fake.store())
        assert indexer.index_nodes([node]) == 1
        sent = json.loads([r for r in fake.requests if r.method == "POST"][0].content)
        assert sent[0]["rag_project_id"] == PROJECT and sent[0]["doc_key"] == "d"

    def test_collection_info_shape(self):
        info = ChunkIndexer(project_id=PROJECT, store=FakeSupabase().store()).get_collection_info()
        assert info["points_count"] == 7 and info["documents_count"] == 2
