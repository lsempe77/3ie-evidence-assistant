"""
Admin Collection Routes

Endpoints for chunk-store management (default project), migrations, and indexing.
"""

import asyncio
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CollectionInfo,
    IngestRequest,
    IngestResponse,
)
from src.config.settings import settings
from src.utils.logging import get_logger

from ..dependencies import (
    COLLECTION_CACHE_TTL,
    get_collection_info_cache,
    get_indexer,
    invalidate_admin_caches,
)

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Collection Management
# =============================================================================

@router.delete("/collection")
async def reset_collection():
    """
    Delete every chunk in the default project (DEFAULT_PROJECT_ID).
    WARNING: This deletes ALL indexed chunks for that project!
    """
    try:
        indexer = get_indexer()
        deleted = await asyncio.to_thread(indexer.delete_collection)
        collection_name = indexer.project_id
        logger.info(f"Deleted {deleted} chunks from project {collection_name}")
        
        # Invalidate cache
        invalidate_admin_caches()
        
        return {
            "success": True,
            "message": f"Collection '{collection_name}' reset successfully",
            "action": "deleted_chunks",
            "deleted": deleted,
        }
    except Exception as e:
        logger.error(f"Failed to reset collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database/reset")
async def reset_database():
    """
    Reset PostgreSQL documents table - deletes ALL document metadata.
    
    WARNING: This deletes all document records from PostgreSQL!
    Use with /collection/reset and /r2/clear for a complete system reset.
    """
    import os
    from sqlalchemy import text
    import src.database.connection as db_conn
    
    if not os.getenv("DATABASE_URL"):
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    if db_conn.async_session is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        async with db_conn.async_session() as session:
            # Get count before delete
            result = await session.execute(text("SELECT COUNT(*) FROM documents"))
            count_before = result.scalar() or 0
            
            # Delete all documents
            await session.execute(text("DELETE FROM documents"))
            await session.commit()
        
        logger.warning(f"Database reset: deleted {count_before} documents from PostgreSQL")
        
        return {
            "success": True,
            "message": f"Deleted {count_before} documents from PostgreSQL",
            "deleted_count": count_before,
        }
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collection")
async def get_collection_info():
    """Get vector collection information. Cached for 30 seconds."""
    cache = get_collection_info_cache()
    
    # Check cache first
    now = time.time()
    if cache["data"] and (now - cache["timestamp"]) < COLLECTION_CACHE_TTL:
        return cache["data"]
    
    try:
        # Wrap sync call with timeout to prevent hanging
        def _get_info():
            indexer = get_indexer()
            return indexer.get_collection_info()
        
        loop = asyncio.get_event_loop()
        info = await asyncio.wait_for(
            loop.run_in_executor(None, _get_info),
            timeout=8.0  # 8 second timeout
        )
        
        # Cache the result
        cache["data"] = info
        cache["timestamp"] = now
        
        return info
    except asyncio.TimeoutError:
        # Return cached data if available, even if stale
        if cache["data"]:
            return cache["data"]
        return {
            "error": "Chunk store connection timeout",
            "name": settings.default_project_id or "",
            "points_count": 0,
            "status": "timeout"
        }
    except Exception as e:
        logger.error(f"Collection info error: {e}")
        return {
            "error": str(e),
            "name": settings.default_project_id or "",
            "points_count": 0,
            "status": "error"
        }


@router.post("/migrate/add-zotero-fields")
async def migrate_add_zotero_fields():
    """
    Add all Zotero-compatible columns to PostgreSQL documents table if they don't exist.
    Safe to call multiple times.
    """
    try:
        from ..dependencies import is_postgres_available, get_db_session
        from sqlalchemy import text
        
        if not is_postgres_available():
            return {"status": "skipped", "message": "PostgreSQL not available"}
        
        db = await get_db_session()
        try:
            # List of all Zotero-compatible columns to add (matches src/database/models.py)
            columns = [
                # Item type
                ("item_type", "VARCHAR(100)"),
                # Identifiers
                ("doi", "VARCHAR(255)"),
                ("isbn", "VARCHAR(50)"),
                ("issn", "VARCHAR(50)"),
                ("url", "TEXT"),
                # Publication info
                ("publication", "VARCHAR(500)"),
                ("journal", "VARCHAR(500)"),
                ("volume", "VARCHAR(50)"),
                ("issue", "VARCHAR(50)"),
                ("pages", "VARCHAR(100)"),
                ("edition", "VARCHAR(100)"),
                # Publisher
                ("publisher", "VARCHAR(500)"),
                ("place", "VARCHAR(255)"),
                # Series
                ("series", "VARCHAR(500)"),
                ("series_number", "VARCHAR(50)"),
                # Book
                ("book_title", "VARCHAR(500)"),
                ("num_pages", "INTEGER"),
                # Report/Thesis
                ("institution", "VARCHAR(500)"),
                ("report_number", "VARCHAR(100)"),
                ("report_type", "VARCHAR(100)"),
                ("thesis_type", "VARCHAR(100)"),
                # Conference
                ("conference_name", "VARCHAR(500)"),
                ("proceedings_title", "VARCHAR(500)"),
                # Access
                ("accessed_date", "VARCHAR(50)"),
                ("abstract", "TEXT"),
                # Metrics
                ("cited_by_count", "INTEGER"),
                ("is_open_access", "BOOLEAN"),
                # Classification
                ("countries", "TEXT[]"),
                ("sectors", "TEXT[]"),
                ("study_type", "VARCHAR(255)"),
                ("intervention_type", "VARCHAR(500)"),
                ("sdgs", "TEXT[]"),
                ("keywords", "TEXT[]"),
                # Processing
                ("chunk_count", "INTEGER DEFAULT 0"),
                ("page_count", "INTEGER DEFAULT 0"),
                ("metadata_source", "VARCHAR(50)"),
                ("metadata_confidence", "FLOAT DEFAULT 0.0"),
                ("needs_review", "BOOLEAN DEFAULT TRUE"),
                ("status", "VARCHAR(50) DEFAULT 'indexed'"),
                # Extra
                ("extra", "JSONB"),
            ]
            
            added = []
            for col_name, col_type in columns:
                try:
                    await db.execute(text(f"ALTER TABLE documents ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    added.append(col_name)
                except Exception as col_error:
                    logger.warning(f"Could not add column {col_name}: {col_error}")
            
            await db.commit()
            logger.info(f"Migration: Zotero columns added successfully: {added}")
            return {"status": "success", "message": f"Zotero columns added: {added}"}
        finally:
            await db.close()
    except Exception as e:
        logger.error(f"Migration error: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/indexes")
async def ensure_indexes():
    """
    Kept for the admin UI. Chunk-store indexes are created by the database migrations
    (supabase/migrations), so there is nothing to do here.
    """
    return {
        "success": True,
        "message": "Indexes are managed by database migrations",
        "indexes": {},
    }


@router.get("/sample-points")
async def sample_points(limit: int = 5):
    """
    Sample a few chunks from the default project to inspect their metadata.
    Useful for debugging what fields are available for filtering/deletion.
    """
    try:
        indexer = get_indexer()
        points = indexer.sample_points(limit=limit)
        return {
            "count": len(points),
            "points": points,
        }
    except Exception as e:
        logger.error(f"Failed to sample points: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _filter_documents_by_role(documents, project_id: str):
    """Replace each document with the ones built from its own-evidence units (`index_role_filter`).

    The units come from the parser's content list in R2 and are labelled by role; noise roles are
    dropped (see `src/ingestion/relevance_filter.py`). Any failure keeps the original markdown
    document, so a missing content list or a model outage cannot drop a document from the index.
    """
    from src.extraction.store_estimates import DEFAULT_MODEL
    from src.ingestion.indexer import doc_key_from
    from src.ingestion.relevance_filter import documents_from_units, filtered_units

    kept_documents = []
    for document in documents:
        meta = document.metadata or {}
        doc_key = doc_key_from(str(meta.get("pdf_name") or meta.get("file_name")
                                    or meta.get("study_id") or document.doc_id or ""))
        try:
            units = await filtered_units(project_id, doc_key, model=DEFAULT_MODEL,
                                         api_key=settings.openrouter_api_key)
        except Exception as e:
            logger.warning(f"Role filter failed for {doc_key}: {e}; keeping its markdown")
            units = []
        built = documents_from_units(units, doc_key) if units else []
        kept_documents.extend(built or [document])
    return kept_documents


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(request: IngestRequest):
    """
    Ingest documents into the vector database.
    
    This is an admin endpoint for re-indexing documents.
    """
    from src.ingestion.chunking import get_chunker
    from src.ingestion.document_loader import DocumentLoader
    from src.ingestion.indexer import ChunkIndexer
    
    start_time = time.time()
    
    try:
        # Load documents
        loader = DocumentLoader(markdown_dir=Path(request.source_path))
        documents = loader.load_all()
        
        if not documents:
            raise HTTPException(status_code=400, detail="No documents found")
        
        # Chunk documents
        chunker = get_chunker("hybrid")
        project_id = request.collection_name or settings.default_project_id
        if not project_id:
            raise HTTPException(status_code=400, detail="Give a project id or set DEFAULT_PROJECT_ID")
        if settings.index_role_filter:
            documents = await _filter_documents_by_role(documents, project_id)
        nodes = chunker.chunk(documents)

        # Index
        indexer = ChunkIndexer(collection_name=project_id)
        if request.recreate:
            indexer.delete_collection()
        indexer.index_nodes(nodes)
        
        # Get final info
        info = indexer.get_collection_info()
        
        elapsed = time.time() - start_time
        
        return IngestResponse(
            status="success",
            documents_processed=len(documents),
            chunks_created=len(nodes),
            collection=CollectionInfo(
                name=info["name"],
                points_count=info["points_count"],
                vectors_count=info["vectors_count"],
                status=info["status"],
            ),
            elapsed_seconds=elapsed,
        )
        
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
