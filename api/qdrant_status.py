"""Deprecated compatibility shim: use api.vector_status instead.

Kept because api/routes/health.py still imports these names. The health check now
reports the Supabase chunk store's status under the old "qdrant" key.
"""

from api.vector_status import (  # noqa: F401
    VectorStoreState as QdrantConnectionState,
    get_vector_store_status_snapshot as get_qdrant_status_snapshot,
    mark_vector_store_healthy as mark_qdrant_healthy,
    warm_up_vector_store as warm_up_qdrant_connection,
)
