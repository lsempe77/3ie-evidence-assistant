"""Vector storage for the 3ie Evidence Assistant (Supabase Postgres + pgvector)."""

from src.vectorstore.chunk_store import (
    ChunkStore,
    ChunkStoreError,
    legacy_collection_to_project_id,
    to_chunk_row,
)

__all__ = ["ChunkStore", "ChunkStoreError", "legacy_collection_to_project_id", "to_chunk_row"]
