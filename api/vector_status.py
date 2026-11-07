"""Chunk-store (Supabase pgvector) connection status tracking and warm-up helpers."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VectorStoreState:
    """Simple container for chunk-store connection health."""

    healthy: bool = False
    last_checked: Optional[datetime] = None
    last_error: Optional[str] = None
    connecting: bool = False


_state = VectorStoreState()
_state_lock = asyncio.Lock()


async def _update_state(*, healthy: bool, error: Optional[str], connecting: Optional[bool] = None) -> None:
    """Update connection state while holding the lock."""
    async with _state_lock:
        _state.healthy = healthy
        _state.last_checked = datetime.utcnow()
        _state.last_error = error
        if connecting is not None:
            _state.connecting = connecting


def _check_vector_store() -> bool:
    """Blocking connectivity check, run in a worker thread."""
    from src.vectorstore import ChunkStore

    store = ChunkStore(timeout=15)
    try:
        return store.ping()
    finally:
        store.close()


async def warm_up_vector_store() -> None:
    """Check the chunk store without blocking startup or health checks."""
    async with _state_lock:
        if _state.connecting:
            logger.debug("Vector store warm-up already in progress; skipping")
            return
        _state.connecting = True

    try:
        await asyncio.to_thread(_check_vector_store)
    except Exception as exc:  # noqa: BLE001 - surface warm-up failures
        logger.warning(f"Vector store warm-up failed: {exc}")
        await _update_state(healthy=False, error=str(exc), connecting=False)
    else:
        logger.info("Vector store reachable during warm-up")
        await _update_state(healthy=True, error=None, connecting=False)


async def mark_vector_store_healthy() -> None:
    """Mark the chunk store as healthy after a successful query."""
    await _update_state(healthy=True, error=None)


async def get_vector_store_status_snapshot() -> VectorStoreState:
    """Return a copy of the current chunk-store connection state."""
    async with _state_lock:
        return VectorStoreState(
            healthy=_state.healthy,
            last_checked=_state.last_checked,
            last_error=_state.last_error,
            connecting=_state.connecting,
        )
