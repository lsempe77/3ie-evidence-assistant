-- =============================================================================
-- 3ie Evidence Assistant: chunk store functions used by the backend and Modal
-- =============================================================================
-- * hybrid_search gains the metadata filters the retriever supports (year range,
--   sector, target population) and can return embeddings for MMR re-ranking.
-- * merge_chunk_metadata: merge a JSON patch into every chunk of one document
--   (replaces Qdrant set_payload).
-- * project_chunk_stats: chunk and document counts for one project.
--
-- All three are callable only by service_role (the backend and Modal), not by
-- browser clients holding the publishable key.
-- =============================================================================

-- Load the pgvector library in this session so its hnsw.* settings are known when the
-- function below declares them (otherwise a non-superuser gets "permission denied to set parameter").
SELECT '[1]'::extensions.vector;

DROP FUNCTION IF EXISTS public.hybrid_search(
    UUID, TEXT, extensions.halfvec, INTEGER, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION, INTEGER, TEXT[]
);

CREATE INDEX IF NOT EXISTS idx_chunks_year ON public.chunks (((metadata->>'year')::int))
    WHERE metadata ? 'year' AND jsonb_typeof(metadata->'year') = 'number';

CREATE OR REPLACE FUNCTION public.hybrid_search(
    p_project_id UUID,
    query_text TEXT,
    query_embedding extensions.halfvec(1536),
    match_count INTEGER DEFAULT 20,
    candidate_count INTEGER DEFAULT 150,
    full_text_weight DOUBLE PRECISION DEFAULT 1.0,
    semantic_weight DOUBLE PRECISION DEFAULT 1.0,
    rrf_k INTEGER DEFAULT 60,
    doc_keys TEXT[] DEFAULT NULL,
    year_min INTEGER DEFAULT NULL,
    year_max INTEGER DEFAULT NULL,
    sectors TEXT[] DEFAULT NULL,
    target_populations TEXT[] DEFAULT NULL,
    with_embeddings BOOLEAN DEFAULT false
)
RETURNS TABLE (
    id UUID,
    doc_key TEXT,
    chunk_index INTEGER,
    content TEXT,
    context_prefix TEXT,
    parent_text TEXT,
    page_start INTEGER,
    page_end INTEGER,
    section TEXT,
    metadata JSONB,
    semantic_rank BIGINT,
    keyword_rank BIGINT,
    semantic_distance DOUBLE PRECISION,
    score DOUBLE PRECISION,
    embedding extensions.halfvec(1536)
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
SET hnsw.ef_search = 200
SET hnsw.iterative_scan = 'relaxed_order'
AS $$
WITH semantic AS (
    SELECT s.id, s.distance, ROW_NUMBER() OVER (ORDER BY s.distance) AS rank_ix
    FROM (
        SELECT c.id, c.embedding <=> query_embedding AS distance
        FROM public.chunks c
        WHERE c.rag_project_id = p_project_id
          AND c.embedding IS NOT NULL
          AND semantic_weight > 0
          AND (doc_keys IS NULL OR c.doc_key = ANY (doc_keys))
          AND (year_min IS NULL OR (jsonb_typeof(c.metadata->'year') = 'number' AND (c.metadata->>'year')::int >= year_min))
          AND (year_max IS NULL OR (jsonb_typeof(c.metadata->'year') = 'number' AND (c.metadata->>'year')::int <= year_max))
          AND (sectors IS NULL OR c.metadata->'sector' ?| sectors OR c.metadata->'sectors' ?| sectors)
          AND (target_populations IS NULL OR c.metadata->'target_population' ?| target_populations)
        ORDER BY c.embedding <=> query_embedding
        LIMIT candidate_count
    ) s
),
keyword AS (
    SELECT k.id, ROW_NUMBER() OVER (ORDER BY k.rank DESC) AS rank_ix
    FROM (
        SELECT c.id, ts_rank_cd(c.fts, q.tsq) AS rank
        FROM public.chunks c, websearch_to_tsquery('english', query_text) AS q(tsq)
        WHERE c.rag_project_id = p_project_id
          AND full_text_weight > 0
          AND c.fts @@ q.tsq
          AND (doc_keys IS NULL OR c.doc_key = ANY (doc_keys))
          AND (year_min IS NULL OR (jsonb_typeof(c.metadata->'year') = 'number' AND (c.metadata->>'year')::int >= year_min))
          AND (year_max IS NULL OR (jsonb_typeof(c.metadata->'year') = 'number' AND (c.metadata->>'year')::int <= year_max))
          AND (sectors IS NULL OR c.metadata->'sector' ?| sectors OR c.metadata->'sectors' ?| sectors)
          AND (target_populations IS NULL OR c.metadata->'target_population' ?| target_populations)
        ORDER BY rank DESC
        LIMIT candidate_count
    ) k
)
SELECT
    c.id, c.doc_key, c.chunk_index, c.content, c.context_prefix, c.parent_text,
    c.page_start, c.page_end, c.section, c.metadata,
    semantic.rank_ix AS semantic_rank,
    keyword.rank_ix AS keyword_rank,
    semantic.distance AS semantic_distance,
    COALESCE(semantic_weight / (rrf_k + semantic.rank_ix), 0.0)
      + COALESCE(full_text_weight / (rrf_k + keyword.rank_ix), 0.0) AS score,
    CASE WHEN with_embeddings THEN c.embedding END AS embedding
FROM semantic
FULL OUTER JOIN keyword ON semantic.id = keyword.id
JOIN public.chunks c ON c.id = COALESCE(semantic.id, keyword.id)
ORDER BY score DESC
LIMIT match_count;
$$;

COMMENT ON FUNCTION public.hybrid_search IS
    'Hybrid retrieval for one project: HNSW cosine + English full-text, fused with reciprocal rank fusion, with optional metadata filters';

CREATE OR REPLACE FUNCTION public.merge_chunk_metadata(
    p_project_id UUID,
    p_doc_key TEXT,
    patch JSONB
)
RETURNS INTEGER
LANGUAGE sql
SET search_path = ''
AS $$
    WITH updated AS (
        UPDATE public.chunks
        SET metadata = metadata || patch
        WHERE rag_project_id = p_project_id AND doc_key = p_doc_key
        RETURNING 1
    )
    SELECT COUNT(*)::INTEGER FROM updated;
$$;

COMMENT ON FUNCTION public.merge_chunk_metadata IS 'Merge a JSON patch into the metadata of every chunk of one document; returns rows updated';

CREATE OR REPLACE FUNCTION public.project_chunk_stats(p_project_id UUID)
RETURNS TABLE (chunk_count BIGINT, document_count BIGINT, embedded_count BIGINT)
LANGUAGE sql
STABLE
SET search_path = ''
AS $$
    SELECT COUNT(*), COUNT(DISTINCT doc_key), COUNT(embedding)
    FROM public.chunks
    WHERE rag_project_id = p_project_id;
$$;

COMMENT ON FUNCTION public.project_chunk_stats IS 'Chunk, document and embedded-chunk counts for one project';

-- Backend-only: browser clients (anon, authenticated) cannot call these through the API.
REVOKE EXECUTE ON FUNCTION public.hybrid_search(
    UUID, TEXT, extensions.halfvec, INTEGER, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION, INTEGER,
    TEXT[], INTEGER, INTEGER, TEXT[], TEXT[], BOOLEAN
) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.merge_chunk_metadata(UUID, TEXT, JSONB) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.project_chunk_stats(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search(
    UUID, TEXT, extensions.halfvec, INTEGER, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION, INTEGER,
    TEXT[], INTEGER, INTEGER, TEXT[], TEXT[], BOOLEAN
) TO service_role;
GRANT EXECUTE ON FUNCTION public.merge_chunk_metadata(UUID, TEXT, JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION public.project_chunk_stats(UUID) TO service_role;
