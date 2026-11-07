-- =============================================================================
-- 3ie Evidence Assistant: remove the last Qdrant artefact from the schema
-- =============================================================================
-- Projects no longer own a vector collection: chunks live in public.chunks and are
-- scoped by rag_project_id. Nothing in the API, Modal or the frontend reads
-- rag_projects.qdrant_collection any more (consolidation plan, step 2c).

DROP TRIGGER IF EXISTS set_qdrant_collection_name ON public.rag_projects;
DROP FUNCTION IF EXISTS public.generate_qdrant_collection_name();
ALTER TABLE public.rag_projects DROP COLUMN IF EXISTS qdrant_collection;
