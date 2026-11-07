"""
3ie Evidence Assistant - Chunk indexer

Writes document chunks and their embeddings to Supabase (the `chunks` table),
replacing the Qdrant indexer. Keyword search needs no client-side work: Postgres
builds the full-text vector from each chunk's text when the row is written.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.ingestion.embeddings import EmbeddingGenerator
from src.utils.logging import get_logger
from src.vectorstore import ChunkStore, legacy_collection_to_project_id

logger = get_logger(__name__)

# Node metadata keys that map onto table columns rather than the metadata JSONB.
_TEXT_KEYS = {"text", "parent_text", "parent_text_full", "contextual_prefix", "text_with_context"}


def doc_key_from(identifier: str) -> str:
    """Normalise 'input-pdfs/a1b2_file.pdf', 'a1b2_file.pdf' or 'a1b2_file' to 'a1b2_file'."""
    base = identifier.replace("\\", "/").rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0] if "." in base else base


class ChunkIndexer:
    """Index and manage one project's chunks."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        store: Optional[ChunkStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        collection_name: Optional[str] = None,  # Legacy 'rag_<hex>' name, mapped to project_id
    ):
        self.project_id = project_id or legacy_collection_to_project_id(collection_name)
        if not self.project_id:
            raise ValueError("ChunkIndexer needs a project_id (or a legacy 'rag_<id>' collection name)")
        self.store = store or ChunkStore()
        self._embedding_generator = embedding_generator

    @property
    def embedding_generator(self) -> EmbeddingGenerator:
        if self._embedding_generator is None:
            self._embedding_generator = EmbeddingGenerator()
        return self._embedding_generator

    # ------------------------------------------------------------------ indexing

    def index_nodes(self, nodes: List, batch_size: int = 200) -> int:
        """
        Index LlamaIndex nodes, embedding any that have no embedding yet.

        Returns the number of chunks written.
        """
        missing = [n for n in nodes if n.embedding is None]
        if missing:
            logger.info(f"Generating embeddings for {len(missing)} nodes")
            self.embedding_generator.embed_nodes(missing)

        rows = [self.node_to_row(node, position) for position, node in enumerate(nodes)]
        written = self.store.upsert_chunks(self.project_id, rows, batch_size=batch_size)
        logger.info(f"Indexed {written} chunks into project {self.project_id}")
        return written

    @staticmethod
    def node_to_row(node, position: int = 0) -> Dict[str, Any]:
        """Convert a LlamaIndex node into a chunk row."""
        meta = dict(node.metadata or {})
        doc_key = doc_key_from(str(
            meta.get("doc_id") or meta.get("document_id") or meta.get("pdf_name")
            or meta.get("source") or meta.get("filename") or node.node_id
        ))
        row: Dict[str, Any] = {
            "doc_key": doc_key,
            "chunk_index": int(meta.get("chunk_index", position)),
            "content": node.get_content(),
            "context_prefix": meta.get("contextual_prefix") or None,
            "parent_text": meta.get("parent_text") or meta.get("parent_text_full") or None,
            "page_start": meta.get("page_start") or meta.get("page_number"),
            "page_end": meta.get("page_end") or meta.get("page_number"),
            "section": meta.get("section"),
            "embedding": node.embedding,
            "metadata": {k: v for k, v in meta.items() if k not in _TEXT_KEYS} | {"node_id": node.node_id},
        }
        return row

    # --------------------------------------------------------------- management

    async def ensure_collection_exists(self) -> None:
        """No-op: all projects share the chunks table. Kept for callers of the old API."""
        return None

    def delete_by_document_id(self, document_id: str) -> int:
        """Delete every chunk of one document (accepts R2 keys, filenames or doc keys)."""
        deleted = self.store.delete_document(self.project_id, doc_key_from(document_id))
        logger.info(f"Deleted {deleted} chunks for {document_id}")
        return deleted

    delete_by_filename = delete_by_document_id

    def delete_collection(self) -> int:
        """Delete every chunk in the project."""
        deleted = self.store.delete_project(self.project_id)
        logger.info(f"Deleted {deleted} chunks for project {self.project_id}")
        return deleted

    async def delete_collection_async(self) -> int:
        return await asyncio.to_thread(self.delete_collection)

    def get_collection_info(self) -> Dict[str, Any]:
        """Chunk statistics, in the shape the old Qdrant info call returned."""
        try:
            stats = self.store.stats(self.project_id)
            return {
                "name": self.project_id,
                "points_count": stats["chunk_count"],
                "vectors_count": stats["embedded_count"],
                "documents_count": stats["document_count"],
                "status": "green",
            }
        except Exception as e:
            logger.error(f"Failed to get chunk stats: {e}")
            return {"error": str(e)}

    def sample_points(self, limit: int = 5) -> List[Dict[str, Any]]:
        """A few chunks, to inspect their metadata."""
        rows = self.store.list_chunks(self.project_id, limit=limit)
        return [{"id": r["id"], "payload": {**(r.get("metadata") or {}), "text": r.get("content")}} for r in rows]
