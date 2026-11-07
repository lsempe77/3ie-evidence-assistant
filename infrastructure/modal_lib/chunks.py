"""
Chunk-store helpers for Modal functions (Supabase Postgres + pgvector).

Replaces the Qdrant helpers. The store client itself is src/vectorstore/chunk_store.py,
mounted into the image next to modal_lib, so the API and Modal share one implementation.
Credentials come from the SUPABASE Modal secret (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
and optionally DEFAULT_PROJECT_ID for the legacy global input-pdfs/ pipeline).
"""

import os
from typing import Optional, Tuple

from src.vectorstore import ChunkStore, legacy_collection_to_project_id


def get_store() -> ChunkStore:
    return ChunkStore(url=os.environ["SUPABASE_URL"], secret_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def default_project_id() -> str:
    """Project used by the legacy global pipeline (input-pdfs/ at the bucket root)."""
    project_id = os.environ.get("DEFAULT_PROJECT_ID", "")
    if not project_id:
        raise RuntimeError("DEFAULT_PROJECT_ID is not set in the SUPABASE Modal secret")
    return project_id


def resolve_project_id(project_id: Optional[str] = None, collection_name: Optional[str] = None) -> str:
    """Project id from an explicit id, a legacy 'rag_<hex>' name, or the default project."""
    return project_id or legacy_collection_to_project_id(collection_name) or default_project_id()


def check_chunks_indexed(doc_id: str, project_id: Optional[str] = None) -> Tuple[bool, int, Optional[str]]:
    """Return (is_indexed, chunk_count, error) for one document."""
    try:
        count = get_store().count(resolve_project_id(project_id), doc_key=doc_id)
        return count > 0, count, None
    except Exception as e:  # noqa: BLE001 - reported to the caller
        return False, 0, str(e)


def delete_doc_chunks(doc_id: str, project_id: Optional[str] = None) -> int:
    """Delete every chunk of one document; returns the number deleted."""
    try:
        deleted = get_store().delete_document(resolve_project_id(project_id), doc_id)
        print(f"  Deleted {deleted} existing chunks for {doc_id}")
        return deleted
    except Exception as e:  # noqa: BLE001 - best effort before re-indexing
        print(f"  Warning: Failed to delete chunks for {doc_id}: {e}")
        return 0


def indexed_doc_keys(project_id: Optional[str] = None) -> set:
    """Document keys that already have chunks in the project."""
    return set(get_store().doc_keys(resolve_project_id(project_id)))
