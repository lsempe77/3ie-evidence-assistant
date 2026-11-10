-- Study-level retrieval (roadmap N1, 10 November 2026).
--
-- Ranking passages one by one let a few long papers fill the pool: on broad questions
-- the reader saw 10 to 52 of the 86 included studies held. A study card is one short
-- text per document (title, design, countries, intervention, opening text), embedded
-- once. Questions first rank whole studies by their cards, then fetch the best
-- passages within each chosen study (passages_for_studies).

SELECT '[1]'::extensions.vector;  -- load pgvector in this session (see 20261107000200)

CREATE TABLE IF NOT EXISTS public.study_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,
    doc_key TEXT NOT NULL,
    card_text TEXT NOT NULL,
    embedding extensions.halfvec(1536),
    fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', card_text)) STORED,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT study_cards_unique_doc UNIQUE (rag_project_id, doc_key)
);

CREATE INDEX IF NOT EXISTS idx_study_cards_project ON public.study_cards(rag_project_id);
CREATE INDEX IF NOT EXISTS idx_study_cards_fts ON public.study_cards USING gin (fts);

COMMENT ON TABLE public.study_cards IS
    'One embedded summary text per document, for ranking whole studies before passages';

-- Server-side only (the API and Modal use the service role).
ALTER TABLE public.study_cards ENABLE ROW LEVEL SECURITY;


CREATE OR REPLACE FUNCTION public.search_study_cards(
    p_project_id UUID,
    query_text TEXT,
    query_embedding extensions.halfvec(1536),
    match_count INTEGER DEFAULT 80,
    full_text_weight DOUBLE PRECISION DEFAULT 1.0,
    semantic_weight DOUBLE PRECISION DEFAULT 1.0,
    rrf_k INTEGER DEFAULT 60
)
RETURNS TABLE (
    doc_key TEXT,
    semantic_rank BIGINT,
    keyword_rank BIGINT,
    semantic_distance DOUBLE PRECISION,
    score DOUBLE PRECISION
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
-- Collections hold hundreds to a few thousand cards, so an exact scan within the
-- project is fast and needs no vector index.
WITH semantic AS (
    SELECT s.doc_key, s.distance, ROW_NUMBER() OVER (ORDER BY s.distance) AS rank_ix
    FROM (
        SELECT sc.doc_key, sc.embedding <=> query_embedding AS distance
        FROM public.study_cards sc
        WHERE sc.rag_project_id = p_project_id AND sc.embedding IS NOT NULL AND semantic_weight > 0
    ) s
),
keyword AS (
    SELECT k.doc_key, ROW_NUMBER() OVER (ORDER BY k.rank DESC) AS rank_ix
    FROM (
        SELECT sc.doc_key, ts_rank_cd(sc.fts, q.tsq) AS rank
        FROM public.study_cards sc, websearch_to_tsquery('english', query_text) AS q(tsq)
        WHERE sc.rag_project_id = p_project_id AND full_text_weight > 0 AND sc.fts @@ q.tsq
    ) k
)
SELECT
    COALESCE(semantic.doc_key, keyword.doc_key) AS doc_key,
    semantic.rank_ix AS semantic_rank,
    keyword.rank_ix AS keyword_rank,
    semantic.distance AS semantic_distance,
    COALESCE(semantic_weight / (rrf_k + semantic.rank_ix), 0.0)
      + COALESCE(full_text_weight / (rrf_k + keyword.rank_ix), 0.0) AS score
FROM semantic
FULL OUTER JOIN keyword ON semantic.doc_key = keyword.doc_key
ORDER BY score DESC
LIMIT match_count;
$$;

COMMENT ON FUNCTION public.search_study_cards IS
    'Rank the studies of one project for a question: cosine on study cards + English full-text, fused with RRF';


CREATE OR REPLACE FUNCTION public.passages_for_studies(
    p_project_id UUID,
    query_embedding extensions.halfvec(1536),
    p_doc_keys TEXT[],
    per_doc INTEGER DEFAULT 4
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
AS $$
-- The best per_doc passages of each listed study, by cosine distance to the question.
-- An exact scan over the chosen studies' chunks (a few thousand rows), so every study
-- gets passages, unlike a global top-k.
SELECT r.id, r.doc_key, r.chunk_index, r.content, r.context_prefix, r.parent_text,
       r.page_start, r.page_end, r.section, r.metadata,
       r.rank_in_doc AS semantic_rank, NULL::BIGINT AS keyword_rank,
       r.distance AS semantic_distance, 1.0 - r.distance AS score
FROM (
    SELECT c.*, c.embedding <=> query_embedding AS distance,
           ROW_NUMBER() OVER (PARTITION BY c.doc_key ORDER BY c.embedding <=> query_embedding) AS rank_in_doc
    FROM public.chunks c
    WHERE c.rag_project_id = p_project_id
      AND c.doc_key = ANY (p_doc_keys)
      AND c.embedding IS NOT NULL
) r
WHERE r.rank_in_doc <= per_doc
ORDER BY r.doc_key, r.rank_in_doc;
$$;

COMMENT ON FUNCTION public.passages_for_studies IS
    'Top passages within each of the given studies of one project, by cosine distance to the question';

REVOKE ALL ON FUNCTION public.search_study_cards(UUID, TEXT, extensions.halfvec, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION, INTEGER) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.passages_for_studies(UUID, extensions.halfvec, TEXT[], INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.search_study_cards(UUID, TEXT, extensions.halfvec, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION, INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION public.passages_for_studies(UUID, extensions.halfvec, TEXT[], INTEGER) TO service_role;
