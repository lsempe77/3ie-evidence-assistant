"""
3ie Evidence Assistant - Chunk store (Supabase Postgres + pgvector)

Replaces the Qdrant client. Talks to the Supabase REST API (PostgREST) with the
secret key, so it needs nothing beyond httpx and runs unchanged in the API, in
scripts and in Modal containers.

Storage lives in the `chunks` table and the `hybrid_search`, `merge_chunk_metadata`
and `project_chunk_stats` functions (supabase/migrations/2026110700*_*.sql).
One table holds every project; `rag_project_id` scopes every call.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx

DEFAULT_TIMEOUT = 60.0
UPSERT_BATCH = 50
UPSERT_ATTEMPTS = 4
UPSERT_BACKOFF_SECONDS = 2.0
PAGE_SIZE = 1000

# Columns of public.chunks that callers may set directly; anything else in a row
# dict goes into the metadata JSONB column.
CHUNK_COLUMNS = {
    "id", "rag_project_id", "document_id", "doc_key", "chunk_index", "content",
    "context_prefix", "parent_text", "page_start", "page_end", "section", "metadata", "embedding",
}


class ChunkStoreError(RuntimeError):
    """Raised when the Supabase API rejects a chunk-store request."""


def _settings_value(name: str) -> str:
    """Read a value from src.config.settings when available, else from the environment."""
    try:
        from src.config.settings import settings  # imported lazily: absent in Modal images
        value = getattr(settings, name.lower(), "") or ""
        if value:
            return value
    except Exception:
        pass
    return os.environ.get(name.upper(), "")


def legacy_collection_to_project_id(collection_name: Optional[str]) -> Optional[str]:
    """Map a legacy Qdrant collection name 'rag_<32 hex>' (or a plain project UUID) to the project UUID."""
    if not collection_name:
        return None
    if len(collection_name) == 36 and collection_name.count("-") == 4:
        return collection_name.lower()
    if not collection_name.startswith("rag_"):
        return None
    raw = collection_name[4:]
    if len(raw) != 32 or any(ch not in "0123456789abcdef" for ch in raw.lower()):
        return None
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def _parse_vector(value: Any) -> Optional[List[float]]:
    """pgvector values arrive over REST as the text '[0.1,0.2,...]'."""
    if value is None:
        return None
    if isinstance(value, str):
        return [float(x) for x in json.loads(value)]
    return [float(x) for x in value]


def _strip_nul(value: Any) -> Any:
    """Remove NUL characters, which Postgres text and JSONB cannot store (22P05)."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {_strip_nul(k): _strip_nul(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_nul(v) for v in value]
    return value


def to_chunk_row(project_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Split a flat chunk dict into table columns plus a metadata JSONB object."""
    out: Dict[str, Any] = {"rag_project_id": project_id, "metadata": dict(row.get("metadata") or {})}
    for key, value in row.items():
        if key == "metadata":
            continue
        if key in CHUNK_COLUMNS:
            out[key] = value
        else:
            out["metadata"][key] = value
    if out.get("embedding") is not None:
        out["embedding"] = [float(x) for x in out["embedding"]]
    out = {k: (v if k == "embedding" else _strip_nul(v)) for k, v in out.items()}
    if "doc_key" not in out or "chunk_index" not in out or "content" not in out:
        raise ValueError("chunk rows need doc_key, chunk_index and content")
    return out


class ChunkStore:
    """Thin client for the chunk table and its search functions."""

    def __init__(
        self,
        url: Optional[str] = None,
        secret_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        url = (url or _settings_value("SUPABASE_URL")).rstrip("/")
        key = secret_key or _settings_value("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ChunkStoreError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        self._client = httpx.Client(
            base_url=f"{url}/rest/v1",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    # ------------------------------------------------------------------ helpers

    def _check(self, response: httpx.Response) -> httpx.Response:
        if response.status_code >= 400:
            raise ChunkStoreError(f"{response.request.method} {response.request.url.path} "
                                  f"failed ({response.status_code}): {response.text[:300]}")
        return response

    def _rpc(self, name: str, params: Dict[str, Any]) -> Any:
        return self._check(self._client.post(f"/rpc/{name}", json=params)).json()

    @staticmethod
    def _count_from(response: httpx.Response) -> int:
        # Content-Range: 0-24/123  or  */123
        total = response.headers.get("content-range", "*/0").rsplit("/", 1)[-1]
        return int(total) if total.isdigit() else 0

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------- writes

    def upsert_chunks(self, project_id: str, rows: Iterable[Dict[str, Any]],
                      batch_size: int = UPSERT_BATCH) -> int:
        """Insert or replace chunks, keyed on (project, doc_key, chunk_index)."""
        prepared = [to_chunk_row(project_id, r) for r in rows]
        for i in range(0, len(prepared), batch_size):
            self._post_with_retry(prepared[i:i + batch_size])
        return len(prepared)

    def _post_with_retry(self, batch: List[Dict[str, Any]]) -> None:
        """
        POST one batch, retrying timeouts and server errors with backoff.

        Each insert also updates the HNSW and full-text indexes. With many workers
        writing at once a batch can exceed the database statement timeout (57014)
        or the client read timeout. The upsert is idempotent, so retrying is safe.
        """
        for attempt in range(UPSERT_ATTEMPTS):
            last = attempt == UPSERT_ATTEMPTS - 1
            try:
                response = self._client.post(
                    "/chunks",
                    params={"on_conflict": "rag_project_id,doc_key,chunk_index"},
                    headers={"Prefer": "return=minimal,resolution=merge-duplicates"},
                    json=batch,
                )
            except httpx.TimeoutException:
                if last:
                    raise
            else:
                if response.status_code < 500 or last:
                    self._check(response)
                    return
            time.sleep(UPSERT_BACKOFF_SECONDS * 2 ** attempt)

    def delete_document(self, project_id: str, doc_key: str) -> int:
        """Delete every chunk of one document; returns the number deleted."""
        response = self._check(self._client.delete(
            "/chunks",
            params={"rag_project_id": f"eq.{project_id}", "doc_key": f"eq.{doc_key}"},
            headers={"Prefer": "return=minimal,count=exact"},
        ))
        return self._count_from(response)

    def delete_project(self, project_id: str) -> int:
        """Delete every chunk of a project; returns the number deleted."""
        response = self._check(self._client.delete(
            "/chunks",
            params={"rag_project_id": f"eq.{project_id}"},
            headers={"Prefer": "return=minimal,count=exact"},
        ))
        return self._count_from(response)

    def merge_metadata(self, project_id: str, doc_key: str, patch: Dict[str, Any]) -> int:
        """Merge `patch` into the metadata of every chunk of one document."""
        return int(self._rpc("merge_chunk_metadata",
                             {"p_project_id": project_id, "p_doc_key": doc_key, "patch": patch}))

    # -------------------------------------------------------------------- reads

    def ping(self) -> bool:
        """Cheap connectivity check: one indexed read of the chunks table."""
        self._check(self._client.get("/chunks", params={"select": "id", "limit": "1"}))
        return True

    def total_chunks(self) -> int:
        """Chunks across all projects (planner estimate; cheap on large tables)."""
        response = self._check(self._client.get(
            "/chunks", params={"select": "id", "limit": "1"}, headers={"Prefer": "count=estimated"},
        ))
        return self._count_from(response)

    def count(self, project_id: str, doc_key: Optional[str] = None) -> int:
        params = {"rag_project_id": f"eq.{project_id}", "select": "id", "limit": "1"}
        if doc_key is not None:
            params["doc_key"] = f"eq.{doc_key}"
        response = self._check(self._client.get("/chunks", params=params, headers={"Prefer": "count=exact"}))
        return self._count_from(response)

    def stats(self, project_id: str) -> Dict[str, int]:
        rows = self._rpc("project_chunk_stats", {"p_project_id": project_id})
        row = rows[0] if rows else {}
        return {k: int(row.get(k) or 0) for k in ("chunk_count", "document_count", "embedded_count")}

    def list_chunks(
        self,
        project_id: str,
        doc_key: Optional[str] = None,
        columns: Sequence[str] = ("id", "doc_key", "chunk_index", "content", "page_start", "page_end", "metadata"),
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return chunks ordered by (doc_key, chunk_index); pages through everything when limit is None."""
        out: List[Dict[str, Any]] = []
        params = {"rag_project_id": f"eq.{project_id}", "select": ",".join(columns),
                  "order": "doc_key.asc,chunk_index.asc"}
        if doc_key is not None:
            params["doc_key"] = f"eq.{doc_key}"
        while True:
            page = min(PAGE_SIZE, limit - len(out)) if limit is not None else PAGE_SIZE
            if page <= 0:
                break
            batch = self._check(self._client.get(
                "/chunks", params={**params, "limit": str(page), "offset": str(offset + len(out))},
            )).json()
            out.extend(batch)
            if len(batch) < page:
                break
        return out

    def doc_keys(self, project_id: str) -> List[str]:
        """Distinct document keys in a project (from chunk 0 of each document)."""
        rows = self._check(self._client.get("/chunks", params={
            "rag_project_id": f"eq.{project_id}", "chunk_index": "eq.0", "select": "doc_key",
            "order": "doc_key.asc", "limit": "100000",
        })).json()
        return [r["doc_key"] for r in rows]

    def hybrid_search(
        self,
        project_id: str,
        query_text: str,
        query_embedding: Sequence[float],
        match_count: int = 20,
        candidate_count: int = 150,
        full_text_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = 60,
        doc_keys: Optional[Sequence[str]] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        sectors: Optional[Sequence[str]] = None,
        target_populations: Optional[Sequence[str]] = None,
        with_embeddings: bool = False,
    ) -> List[Dict[str, Any]]:
        """Hybrid (vector + full-text) search fused with reciprocal rank fusion."""
        params: Dict[str, Any] = {
            "p_project_id": project_id,
            "query_text": query_text,
            "query_embedding": json.dumps([float(x) for x in query_embedding]),
            "match_count": match_count,
            "candidate_count": max(candidate_count, match_count),
            "full_text_weight": full_text_weight,
            "semantic_weight": semantic_weight,
            "rrf_k": rrf_k,
            "with_embeddings": with_embeddings,
        }
        optional = {"doc_keys": doc_keys, "year_min": year_min, "year_max": year_max,
                    "sectors": sectors, "target_populations": target_populations}
        params.update({k: (list(v) if isinstance(v, (list, tuple)) else v)
                       for k, v in optional.items() if v})
        rows = self._rpc("hybrid_search", params)
        for row in rows:
            row["embedding"] = _parse_vector(row.get("embedding"))
        return rows
