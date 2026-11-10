-- Find each study's estimates closest to a question (roadmap N6 step 2).
-- Each estimate's outcome text (outcome, arm, subgroup) is embedded once; at question
-- time the reader gets the per_doc closest estimates of every study it reads.

SELECT '[1]'::extensions.vector;  -- load pgvector in this session (see 20261107000200)

ALTER TABLE public.effect_estimates ADD COLUMN IF NOT EXISTS embedding extensions.halfvec(1536);

CREATE OR REPLACE FUNCTION public.estimates_for_studies(
    p_project_id UUID,
    query_embedding extensions.halfvec(1536),
    p_doc_keys TEXT[],
    per_doc INTEGER DEFAULT 12,
    p_source TEXT DEFAULT 'tables_v1'
)
RETURNS TABLE (
    id UUID, doc_key TEXT, table_number TEXT, outcome_name TEXT, treatment_arm TEXT, subgroup TEXT,
    effect_size DOUBLE PRECISION, standard_error DOUBLE PRECISION, p_value DOUBLE PRECISION, p_text TEXT,
    ci_text TEXT, sample_size INTEGER, literal_text TEXT, page INTEGER, distance DOUBLE PRECISION
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
SELECT r.id, r.doc_key, r.table_number, r.outcome_name, r.treatment_arm, r.subgroup, r.effect_size,
       r.standard_error, r.p_value, r.p_text, r.ci_text, r.sample_size, r.literal_text, r.page, r.distance
FROM (
    SELECT e.*, e.embedding <=> query_embedding AS distance,
           ROW_NUMBER() OVER (PARTITION BY e.doc_key ORDER BY e.embedding <=> query_embedding) AS rank_in_doc
    FROM public.effect_estimates e
    WHERE e.rag_project_id = p_project_id
      AND e.doc_key = ANY (p_doc_keys)
      AND e.source = p_source
      AND e.embedding IS NOT NULL
) r
WHERE r.rank_in_doc <= per_doc
ORDER BY r.doc_key, r.distance;
$$;

REVOKE ALL ON FUNCTION public.estimates_for_studies(UUID, extensions.halfvec, TEXT[], INTEGER, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.estimates_for_studies(UUID, extensions.halfvec, TEXT[], INTEGER, TEXT) TO service_role;
