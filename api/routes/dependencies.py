"""
3ie Evidence Assistant - Shared Route Dependencies

Common dependencies, singletons, and utilities used across route modules.
"""

import asyncio
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from src.agents.evidence_assistant_agent import EvidenceAssistantAgent
from src.config.settings import settings
from src.ingestion.indexer import ChunkIndexer
from src.retrieval.hybrid_retriever import HybridRetriever
from src.utils.logging import get_logger

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)

# =============================================================================
# Admin Authentication
# =============================================================================

# API Key header scheme (for programmatic access)
api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)

# Session token header (for browser-based access after login)
session_header = APIKeyHeader(name="X-Admin-Session", auto_error=False)

# In-memory session store (for production, use Redis or database)
# Format: {token: {"expires": timestamp, "created": timestamp}}
_admin_sessions: dict[str, dict] = {}

# Session duration: 24 hours
SESSION_DURATION_SECONDS = 24 * 60 * 60


def _generate_session_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def _clean_expired_sessions():
    """Remove expired sessions from memory."""
    now = time.time()
    expired = [token for token, data in _admin_sessions.items() if data["expires"] < now]
    for token in expired:
        del _admin_sessions[token]


def create_admin_session() -> tuple[str, int]:
    """
    Create a new admin session.
    
    Returns:
        Tuple of (session_token, expires_in_seconds)
    """
    _clean_expired_sessions()
    
    token = _generate_session_token()
    expires = time.time() + SESSION_DURATION_SECONDS
    
    _admin_sessions[token] = {
        "expires": expires,
        "created": time.time(),
    }
    
    logger.info(f"Created admin session (expires in {SESSION_DURATION_SECONDS}s)")
    return token, SESSION_DURATION_SECONDS


def verify_session_token(token: str) -> bool:
    """Check if a session token is valid and not expired."""
    if not token or token not in _admin_sessions:
        return False
    
    session = _admin_sessions[token]
    if session["expires"] < time.time():
        del _admin_sessions[token]
        return False
    
    return True


def invalidate_session(token: str) -> bool:
    """Invalidate (logout) a session token."""
    if token in _admin_sessions:
        del _admin_sessions[token]
        return True
    return False


async def verify_admin_auth(
    api_key: str = Security(api_key_header),
    session_token: str = Security(session_header),
) -> str:
    """
    Verify admin authentication via API key OR session token.
    
    Supports two authentication methods:
    1. X-Admin-API-Key header (for programmatic/CI access)
    2. X-Admin-Session header (for browser access after login)
    
    Raises HTTPException 401 if neither method succeeds.
    
    If ADMIN_PASSWORD is not set, authentication is disabled (development mode).
    """
    admin_password = settings.admin_password
    admin_api_key = settings.admin_api_key
    
    # If no admin password configured, allow access (development mode)
    if not admin_password and not admin_api_key:
        logger.warning("ADMIN_PASSWORD not set - admin routes are unprotected!")
        return "development"
    
    # Check session token first (browser login)
    if session_token and verify_session_token(session_token):
        return "session"
    
    # Check API key (programmatic access)
    if api_key and admin_api_key and api_key == admin_api_key:
        return "api_key"
    
    # Neither method worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please log in at /admin/login",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Alias for backward compatibility
verify_admin_api_key = verify_admin_auth


# =============================================================================
# Multi-Tenant Authentication (Supabase)
# =============================================================================

from src.auth import is_multi_tenant_enabled, get_current_user as supabase_get_current_user, AuthenticatedUser


async def get_current_user_or_legacy(
    api_key: str = Security(api_key_header),
    session_token: str = Security(session_header),
) -> Optional[AuthenticatedUser]:
    """
    Get current authenticated user.
    
    In multi-tenant mode (Supabase configured):
        - Returns AuthenticatedUser from JWT token
        
    In legacy mode (single-tenant):
        - Falls back to API key / session token auth
        - Returns None (caller should use legacy indexer)
    """
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    
    if is_multi_tenant_enabled():
        # Import here to avoid circular imports
        from src.auth.supabase_auth import bearer_scheme, verify_supabase_token
        # We need to get the bearer token from the request
        # For now, check if session_token looks like a JWT (Supabase tokens are JWTs)
        if session_token and "." in session_token:
            user = verify_supabase_token(session_token)
            if user:
                return user
    
    # Legacy mode - verify with API key or session
    admin_password = settings.admin_password
    admin_api_key = settings.admin_api_key
    
    if not admin_password and not admin_api_key:
        return None  # Development mode
    
    if session_token and verify_session_token(session_token):
        return None  # Legacy session - no user object
    
    if api_key and admin_api_key and api_key == admin_api_key:
        return None  # Legacy API key - no user object
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_indexer_for_user(user: Optional[AuthenticatedUser], rag_project_id: Optional[str] = None) -> ChunkIndexer:
    """
    Get an indexer for the user's context.
    
    In multi-tenant mode:
        - Requires rag_project_id and validates that the user owns the project
        
    In legacy mode:
        - Uses the default project (DEFAULT_PROJECT_ID)
    """
    if user and rag_project_id and is_multi_tenant_enabled():
        # Multi-tenant: get collection from database
        from src.auth import get_supabase_client
        client = get_supabase_client()
        
        result = client.table("rag_projects").select("id").eq("id", rag_project_id).eq("user_id", user.id).single().execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RAG project not found"
            )
        
        return ChunkIndexer(project_id=result.data["id"])
    
    # Legacy mode: use default collection
    return get_indexer()


# =============================================================================
# Global Singletons
# =============================================================================

_agent: Optional[EvidenceAssistantAgent] = None
_indexer: Optional[ChunkIndexer] = None
_collection_agents: dict[str, EvidenceAssistantAgent] = {}


def get_agent(collection_name: Optional[str] = None) -> EvidenceAssistantAgent:
    """Get or create the agent instance.
    
    Args:
        collection_name: Project id, or the project's legacy 'rag_<hex>' name, for
                        multi-tenant RAGs. If None, uses the default project.
    """
    global _agent, _collection_agents
    
    if collection_name:
        # Multi-tenant: create/cache agent per collection
        if collection_name not in _collection_agents:
            # Create agent with custom collection retriever
            _collection_agents[collection_name] = EvidenceAssistantAgent(
                retriever=HybridRetriever(collection_name=collection_name),
            )
        return _collection_agents[collection_name]
    
    # Default single-tenant agent
    if _agent is None:
        _agent = EvidenceAssistantAgent()
    return _agent


def get_indexer() -> ChunkIndexer:
    """Get or create the indexer for the default project (DEFAULT_PROJECT_ID)."""
    global _indexer
    if _indexer is None:
        if not settings.default_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No project given and DEFAULT_PROJECT_ID is not configured",
            )
        _indexer = ChunkIndexer(project_id=settings.default_project_id)
    return _indexer


# =============================================================================
# Database (PostgreSQL)
# =============================================================================

def is_postgres_available() -> bool:
    """Check if PostgreSQL is configured and available."""
    return bool(os.getenv("DATABASE_URL"))


async def get_db_session():
    """Get database session if available. Returns None if not configured."""
    if not is_postgres_available():
        return None
    
    try:
        # Import the module to access the current value of async_session
        # (not a cached import-time value)
        import src.database.connection as db_conn
        if db_conn.async_session is None:
            return None
        return db_conn.async_session()
    except Exception:
        return None


# =============================================================================
# R2 Client
# =============================================================================

def get_r2_client():
    """Create S3 client configured for Cloudflare R2."""
    account_id = os.getenv("R2_ACCOUNT_ID", "667549da0201b12a53872d803b9880b6")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    
    if not access_key or not secret_key:
        raise HTTPException(
            status_code=500,
            detail="R2 credentials not configured. Set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY."
        )
    
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


# =============================================================================
# Cache Management
# =============================================================================

# Cache for collection info (refreshes every 30 seconds)
_collection_info_cache = {
    "data": None,
    "timestamp": 0
}
COLLECTION_CACHE_TTL = 30  # seconds

# Longer cache TTL because scanning 400K+ vectors is expensive
DOCUMENTS_CACHE_TTL = 300  # 5 minutes
_documents_cache = {
    "data": None,
    "timestamp": 0,
    "search": None,
    "status": None,
}

METADATA_CACHE_TTL = 30  # seconds
_metadata_cache = {
    "data": None,
    "timestamp": 0,
    "filter": None,
}


def get_collection_info_cache():
    """Get the collection info cache."""
    return _collection_info_cache


def get_documents_cache():
    """Get the documents cache."""
    return _documents_cache


def get_metadata_cache():
    """Get the metadata cache."""
    return _metadata_cache


def invalidate_admin_caches() -> None:
    """Clear lightweight admin caches after mutations."""
    _documents_cache["data"] = None
    _documents_cache["timestamp"] = 0
    _metadata_cache["data"] = None
    _metadata_cache["timestamp"] = 0


# =============================================================================
# Modal Processing Trigger
# =============================================================================

async def trigger_modal_processing(force_reprocess: bool = False, max_documents: int = 10):
    """Helper to trigger Modal processing via webhook."""
    import httpx
    
    # Modal web endpoint URL
    modal_trigger_url = settings.modal_trigger_url
    
    try:
        # Longer timeout (90s) to handle Modal cold starts
        # Modal functions can take 30-60s to spin up from cold
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                modal_trigger_url,
                json={
                    "force_reprocess": force_reprocess,
                    "check_qdrant": True,
                    "max_documents": max_documents,
                },
                headers={"Content-Type": "application/json"},
            )
            logger.info(f"Triggered Modal processing via {modal_trigger_url}: {response.status_code}")
            return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Failed to trigger Modal processing: {e}")
        raise  # Re-raise so caller knows it failed


# =============================================================================
# Project access control (chat, query and chat history)
# =============================================================================

def resolve_project(project_ref: str) -> Optional[dict]:
    """
    Find a project by UUID, legacy 'rag_<hex>' name, or slug.

    Returns the rag_projects row (id, user_id, is_public, name, slug, description, document_count) or None.
    """
    from src.auth import get_supabase_client
    from src.vectorstore import legacy_collection_to_project_id

    client = get_supabase_client()
    columns = "id, user_id, is_public, name, slug, description, document_count"
    project_id = legacy_collection_to_project_id(project_ref)
    if project_id:
        result = client.table("rag_projects").select(columns).eq("id", project_id).execute()
        if result.data:
            return result.data[0]
    result = client.table("rag_projects").select(columns).eq("slug", project_ref).execute()
    return result.data[0] if result.data else None


def authorize_project(project_ref: str, user: Optional[AuthenticatedUser]) -> dict:
    """
    Return the project if the caller may read it: public projects are open to
    everyone, private projects only to their owner. Raises 404 or 403 otherwise.
    """
    project = resolve_project(project_ref)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.get("is_public"):
        return project
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to use this project")
    if str(project.get("user_id")) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This project is private")
    return project
