-- =============================================================================
-- 3ie Evidence Assistant: document chunks with hybrid (vector + full-text) search
-- =============================================================================
-- Replaces Qdrant (docs/SUPABASE_CONSOLIDATION_PLAN.md, Phase 1).
--
-- * One table for all projects; per-project isolation is a rag_project_id filter.
-- * Child chunks (~200 words) are embedded; parent_text carries the wider context
--   used for synthesis, as the Qdrant payload did.
-- * Embeddings: Cohere embed-v4.0, 1,536 dimensions, stored as halfvec (2 bytes per
--   dimension, about 3 KB per chunk) with an HNSW cosine index.
-- * Keyword side: a stored English tsvector over context prefix + chunk text,
--   replacing Qdrant's BM25-style sparse vectors.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS public.chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,

    -- Stable document key used across R2 and the parser outputs (the old Qdrant doc_id)
    doc_key TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,

    content TEXT NOT NULL,
    context_prefix TEXT,
    parent_text TEXT,

    page_start INTEGER,
    page_end INTEGER,
    section TEXT,

    -- Bibliographic and classification fields (title, authors, year, doi, study_design, ...)
    metadata JSONB NOT NULL DEFAULT '{}',

    embedding extensions.halfvec(1536),
    fts TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(context_prefix, '') || ' ' || content)
    ) STORED,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chunks_unique_position UNIQUE (rag_project_id, doc_key, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_project_doc ON public.chunks(rag_project_id, doc_key);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON public.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON public.chunks USING gin (fts);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON public.chunks
    USING hnsw (embedding extensions.halfvec_cosine_ops) WITH (m = 16, ef_construction = 200);

COMMENT ON TABLE public.chunks IS 'Embedded document chunks for retrieval (replaces Qdrant)';

ALTER TABLE public.chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view chunks in own or public projects" ON public.chunks
    FOR SELECT TO anon, authenticated
    USING (rag_project_id IN (
        SELECT id FROM public.rag_projects
        WHERE is_public = true OR user_id = (SELECT auth.uid())
    ));
-- Writes happen only through the backend and Modal with the secret key (service_role).

-- =============================================================================
-- hybrid_search: reciprocal rank fusion of vector and full-text rankings
-- =============================================================================
-- Each side retrieves up to `candidate_count` rows for the project; the two ranked
-- lists are fused with RRF and the top `match_count` rows are returned with their
-- individual ranks, so the caller can log or inspect them. Pass full_text_weight = 0
-- for vector-only search, semantic_weight = 0 for keyword-only.

CREATE OR REPLACE FUNCTION public.hybrid_search(
    p_project_id UUID,
    query_text TEXT,
    query_embedding extensions.halfvec(1536),
    match_count INTEGER DEFAULT 20,
    candidate_count INTEGER DEFAULT 150,
    full_text_weight DOUBLE PRECISION DEFAULT 1.0,
    semantic_weight DOUBLE PRECISION DEFAULT 1.0,
    rrf_k INTEGER DEFAULT 60,
    doc_keys TEXT[] DEFAULT NULL
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
    score DOUBLE PRECISION
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
          AND (doc_keys IS NULL OR c.doc_key = ANY (doc_keys))
          AND semantic_weight > 0
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
          AND c.fts @@ q.tsq
          AND (doc_keys IS NULL OR c.doc_key = ANY (doc_keys))
          AND full_text_weight > 0
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
      + COALESCE(full_text_weight / (rrf_k + keyword.rank_ix), 0.0) AS score
FROM semantic
FULL OUTER JOIN keyword ON semantic.id = keyword.id
JOIN public.chunks c ON c.id = COALESCE(semantic.id, keyword.id)
ORDER BY score DESC
LIMIT match_count;
$$;

COMMENT ON FUNCTION public.hybrid_search IS
    'Hybrid retrieval for one project: HNSW cosine search + English full-text search fused with reciprocal rank fusion';
