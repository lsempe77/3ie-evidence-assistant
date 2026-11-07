-- =============================================================================
-- 3ie Evidence Assistant: baseline schema (fresh start, 7 November 2026)
-- =============================================================================
-- Consolidates the schema that was previously spread across supabase/schema.sql,
-- scripts/migrations/*.sql and supabase/migrations/*.sql (now in supabase/legacy/).
--
-- Changes from the legacy files, made deliberately for the fresh project:
--   * extensions are created explicitly (pgcrypto, pg_trgm) in the `extensions` schema
--   * service-role policies use `TO service_role` instead of checking the JWT role claim,
--     which also works with the new sb_secret_ API keys
--   * views are created WITH (security_invoker = true), so they respect the caller's RLS
--     (previously usage_daily_summary exposed every user's usage to any signed-in user)
--   * chat_history no longer lets any caller read or delete anonymous rows
--   * one-off UPDATE / SELECT statements from the old migrations are dropped
--
-- All application data access goes through the FastAPI backend with the secret key
-- (service_role, which bypasses RLS). The RLS policies are defence in depth.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pg_trgm  WITH SCHEMA extensions;

-- =============================================================================
-- Shared trigger function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- =============================================================================
-- rag_projects
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.rag_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    description TEXT,
    slug TEXT UNIQUE,

    -- Kept until the code no longer reads it (consolidation plan, Phase 2), then dropped.
    qdrant_collection TEXT UNIQUE,

    is_public BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'processing', 'error', 'deleted')),

    document_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,

    -- Per-project LLM settings (was scripts/migrations/002_model_config.sql)
    model_config JSONB NOT NULL DEFAULT '{
      "provider": "openai",
      "model": "gpt-4o-mini",
      "temperature": 0.1,
      "reasoning_model": "gpt-4o"
    }'::jsonb,

    -- Prompt customisation (was scripts/migrations/003_prompt_config.sql)
    context_prompt TEXT,
    custom_prompts JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_rag_projects_user_id ON public.rag_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_projects_is_public ON public.rag_projects(is_public) WHERE is_public = true;
CREATE INDEX IF NOT EXISTS idx_rag_projects_model_provider ON public.rag_projects ((model_config->>'provider'));

COMMENT ON COLUMN public.rag_projects.model_config IS 'LLM configuration for this project: {provider, model, temperature, reasoning_model}';
COMMENT ON COLUMN public.rag_projects.context_prompt IS 'Domain-specific instructions prepended to all synthesis prompts';
COMMENT ON COLUMN public.rag_projects.custom_prompts IS 'Advanced: custom extraction/synthesis prompts. May affect citation quality.';

-- Legacy behaviour: fill qdrant_collection with rag_<id> when not provided.
CREATE OR REPLACE FUNCTION public.generate_qdrant_collection_name()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    IF NEW.qdrant_collection IS NULL THEN
        NEW.qdrant_collection := 'rag_' || REPLACE(NEW.id::TEXT, '-', '');
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER set_qdrant_collection_name
    BEFORE INSERT ON public.rag_projects
    FOR EACH ROW EXECUTE FUNCTION public.generate_qdrant_collection_name();

CREATE TRIGGER update_rag_projects_updated_at
    BEFORE UPDATE ON public.rag_projects
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- documents
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,

    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size_bytes BIGINT,
    mime_type TEXT,

    status TEXT NOT NULL DEFAULT 'pending'
        CONSTRAINT documents_status_check
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'no_pdf')),
    error_message TEXT,

    r2_input_key TEXT,
    r2_output_key TEXT,

    metadata JSONB NOT NULL DEFAULT '{}',
    chunk_count INTEGER NOT NULL DEFAULT 0,

    -- Bibliography import (was supabase/migrations/003_bibliography_import.sql)
    import_source TEXT,
    match_confidence FLOAT CONSTRAINT check_match_confidence
        CHECK (match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)),
    external_id TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_rag_project_id ON public.documents(rag_project_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON public.documents(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_filename_project ON public.documents(filename, rag_project_id);
CREATE INDEX IF NOT EXISTS idx_documents_external_id ON public.documents(external_id) WHERE external_id IS NOT NULL;

COMMENT ON COLUMN public.documents.status IS 'pending, processing, completed, failed, or no_pdf (Zotero items without a PDF)';
COMMENT ON COLUMN public.documents.import_source IS 'Source of the document: upload, zotero, ris, bibtex, csv';
COMMENT ON COLUMN public.documents.match_confidence IS 'Auto-matching confidence score 0.0-1.0';
COMMENT ON COLUMN public.documents.external_id IS 'External identifier: Zotero key, DOI, cite key';

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON public.documents
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Keep document/chunk counts on rag_projects in step with documents.
CREATE OR REPLACE FUNCTION public.update_rag_project_stats()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
    pid UUID := COALESCE(NEW.rag_project_id, OLD.rag_project_id);
BEGIN
    UPDATE public.rag_projects
    SET document_count = (SELECT COUNT(*) FROM public.documents WHERE rag_project_id = pid),
        chunk_count    = (SELECT COALESCE(SUM(chunk_count), 0) FROM public.documents WHERE rag_project_id = pid)
    WHERE id = pid;
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER update_rag_stats_on_document_change
    AFTER INSERT OR UPDATE OR DELETE ON public.documents
    FOR EACH ROW EXECUTE FUNCTION public.update_rag_project_stats();

-- =============================================================================
-- processing_jobs
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,

    job_type TEXT NOT NULL CHECK (job_type IN ('ingest', 'reprocess', 'delete', 'embed')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),

    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    message TEXT,
    error_message TEXT,
    external_job_id TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_processing_jobs_rag_project_id ON public.processing_jobs(rag_project_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON public.processing_jobs(status);

-- =============================================================================
-- zotero_connections
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.zotero_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,

    api_key TEXT NOT NULL,
    zotero_user_id TEXT NOT NULL,
    library_type TEXT NOT NULL DEFAULT 'user',

    selected_collection_key TEXT,
    auto_sync_enabled BOOLEAN NOT NULL DEFAULT false,
    sync_pdfs BOOLEAN NOT NULL DEFAULT true,

    last_synced_at TIMESTAMPTZ,
    last_sync_version INTEGER,
    total_items_synced INTEGER NOT NULL DEFAULT 0,

    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    connected_by UUID REFERENCES auth.users(id),
    last_sync_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_rag_project_zotero UNIQUE (rag_project_id),
    CONSTRAINT valid_library_type CHECK (library_type IN ('user', 'group'))
);

COMMENT ON TABLE public.zotero_connections IS 'Zotero API credentials and sync configuration per project';

CREATE TRIGGER zotero_connections_updated_at
    BEFORE UPDATE ON public.zotero_connections
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- chat_history
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,  -- NULL for anonymous public users
    session_id TEXT,

    query TEXT NOT NULL,
    study_count INTEGER DEFAULT 0,
    answer TEXT,
    citations_used INTEGER,
    response_data JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_rag_project_id ON public.chat_history(rag_project_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON public.chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON public.chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON public.chat_history(created_at DESC);

COMMENT ON COLUMN public.chat_history.answer IS 'The AI-generated answer to the user query';
COMMENT ON COLUMN public.chat_history.citations_used IS 'Number of citations/sources referenced in the answer';
COMMENT ON COLUMN public.chat_history.response_data IS 'Full cached response (citations, studies, suggestions, evidenceHealth)';

-- =============================================================================
-- usage_logs
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    rag_project_id UUID REFERENCES public.rag_projects(id) ON DELETE SET NULL,

    event_type TEXT NOT NULL,
    provider TEXT,
    model TEXT,

    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    total_tokens INT GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    latency_ms INT,

    metadata JSONB DEFAULT '{}',
    query_text TEXT,
    query_id TEXT,
    session_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON public.usage_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id ON public.usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_rag_project_id ON public.usage_logs(rag_project_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_event_type ON public.usage_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_usage_logs_model ON public.usage_logs(model);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_event ON public.usage_logs(created_at, event_type);

COMMENT ON TABLE public.usage_logs IS 'API usage (LLM calls, embeddings, reranking) for cost and usage analytics';

CREATE OR REPLACE VIEW public.usage_daily_summary WITH (security_invoker = true) AS
SELECT
    date_trunc('day', created_at)::date AS day,
    event_type,
    model,
    COUNT(*) AS count,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    SUM(cost_usd) AS total_cost_usd,
    AVG(latency_ms) AS avg_latency_ms,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(DISTINCT rag_project_id) AS unique_projects
FROM public.usage_logs
GROUP BY date_trunc('day', created_at), event_type, model
ORDER BY day DESC, event_type, model;

CREATE OR REPLACE VIEW public.usage_user_summary WITH (security_invoker = true) AS
SELECT
    user_id,
    COUNT(*) AS total_events,
    COUNT(DISTINCT rag_project_id) AS projects_used,
    SUM(CASE WHEN event_type = 'query' THEN 1 ELSE 0 END) AS query_count,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    SUM(cost_usd) AS total_cost_usd,
    MIN(created_at) AS first_activity,
    MAX(created_at) AS last_activity
FROM public.usage_logs
GROUP BY user_id;

-- =============================================================================
-- evaluation_runs and query_quality_logs (admin only)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.evaluation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type TEXT NOT NULL DEFAULT 'manual',
    evaluator TEXT NOT NULL DEFAULT 'minicheck',
    collection_name TEXT,

    faithfulness FLOAT,
    citation_recall FLOAT,
    citation_precision FLOAT,
    overall_score FLOAT,

    num_queries INTEGER DEFAULT 0,
    num_successful INTEGER DEFAULT 0,
    avg_latency_ms FLOAT,
    details JSONB,

    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    triggered_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_created_at ON public.evaluation_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_evaluator ON public.evaluation_runs(evaluator);

CREATE TABLE IF NOT EXISTS public.query_quality_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID,
    rag_project_id UUID REFERENCES public.rag_projects(id) ON DELETE SET NULL,
    user_id UUID,

    query TEXT NOT NULL,
    answer_preview TEXT,
    num_sources INTEGER,
    num_citations INTEGER,

    faithfulness FLOAT,
    citation_recall FLOAT,
    citation_precision FLOAT,

    was_sampled BOOLEAN DEFAULT false,
    sample_reason TEXT,
    latency_ms FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_query_quality_logs_created_at ON public.query_quality_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_quality_logs_sampled ON public.query_quality_logs(was_sampled) WHERE was_sampled = true;

COMMENT ON TABLE public.evaluation_runs IS 'Results from evaluation suite runs for quality monitoring';
COMMENT ON TABLE public.query_quality_logs IS 'Quality metrics for sampled production queries';

CREATE OR REPLACE VIEW public.evaluation_metrics_summary WITH (security_invoker = true) AS
SELECT
    evaluator,
    COUNT(*) AS total_runs,
    ROUND(AVG(faithfulness)::numeric, 3) AS avg_faithfulness,
    ROUND(AVG(citation_recall)::numeric, 3) AS avg_citation_recall,
    ROUND(AVG(citation_precision)::numeric, 3) AS avg_citation_precision,
    ROUND(AVG(overall_score)::numeric, 3) AS avg_overall,
    MAX(created_at) AS last_run
FROM public.evaluation_runs
WHERE completed_at IS NOT NULL
GROUP BY evaluator;

CREATE OR REPLACE VIEW public.evaluation_trend WITH (security_invoker = true) AS
SELECT
    DATE(created_at) AS run_date,
    evaluator,
    ROUND(AVG(faithfulness)::numeric, 3) AS faithfulness,
    ROUND(AVG(citation_recall)::numeric, 3) AS citation_recall,
    ROUND(AVG(citation_precision)::numeric, 3) AS citation_precision,
    ROUND(AVG(overall_score)::numeric, 3) AS overall_score
FROM public.evaluation_runs
WHERE created_at >= NOW() - INTERVAL '30 days'
  AND completed_at IS NOT NULL
GROUP BY DATE(created_at), evaluator
ORDER BY run_date DESC;

-- =============================================================================
-- extracted_estimates
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.extracted_estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    study_id TEXT NOT NULL,
    document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
    rag_project_id UUID REFERENCES public.rag_projects(id) ON DELETE CASCADE,

    table_number TEXT,
    table_caption TEXT,
    page_number INTEGER,
    pdf_name TEXT,

    treatment_arm TEXT NOT NULL,
    outcome_name TEXT NOT NULL,
    outcome_category TEXT,

    coefficient DOUBLE PRECISION,
    standard_error DOUBLE PRECISION,
    p_value DOUBLE PRECISION,
    ci_lower DOUBLE PRECISION,
    ci_upper DOUBLE PRECISION,

    sample_size INTEGER,
    n_treatment INTEGER,
    n_control INTEGER,

    control_mean DOUBLE PRECISION,
    control_sd DOUBLE PRECISION,

    cohens_d DOUBLE PRECISION,
    hedges_g DOUBLE PRECISION,
    effect_size_assumption TEXT,

    is_main_effect BOOLEAN DEFAULT true,
    is_subgroup BOOLEAN DEFAULT false,
    subgroup_variable TEXT,

    authors TEXT,
    year INTEGER,
    country TEXT,
    study_design TEXT,

    extraction_confidence DOUBLE PRECISION,
    extraction_method TEXT DEFAULT 'pipeline',
    extraction_version TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    effect_summary TEXT GENERATED ALWAYS AS (
        COALESCE(treatment_arm, 'Treatment') || ' effect on ' ||
        COALESCE(outcome_name, 'outcome') || ': ' ||
        COALESCE(coefficient::TEXT, 'N/A') ||
        CASE WHEN standard_error IS NOT NULL THEN ' (SE: ' || standard_error::TEXT || ')' ELSE '' END ||
        CASE WHEN p_value IS NOT NULL THEN ', p=' || p_value::TEXT ELSE '' END ||
        CASE WHEN cohens_d IS NOT NULL THEN ', d=' || ROUND(cohens_d::NUMERIC, 3)::TEXT ELSE '' END
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_extracted_estimates_study_id ON public.extracted_estimates(study_id);
CREATE INDEX IF NOT EXISTS idx_extracted_estimates_document_id ON public.extracted_estimates(document_id);
CREATE INDEX IF NOT EXISTS idx_extracted_estimates_rag_project_id ON public.extracted_estimates(rag_project_id);
CREATE INDEX IF NOT EXISTS idx_extracted_estimates_outcome_category ON public.extracted_estimates(outcome_category);
CREATE INDEX IF NOT EXISTS idx_extracted_estimates_country ON public.extracted_estimates(country);
CREATE INDEX IF NOT EXISTS idx_extracted_estimates_study_design ON public.extracted_estimates(study_design);
CREATE INDEX IF NOT EXISTS idx_extracted_estimates_is_main_effect ON public.extracted_estimates(is_main_effect) WHERE is_main_effect = true;
CREATE INDEX IF NOT EXISTS idx_extracted_estimates_outcome_name_trgm
    ON public.extracted_estimates USING gin (outcome_name extensions.gin_trgm_ops);

COMMENT ON TABLE public.extracted_estimates IS 'Effect sizes extracted from study PDFs for quantitative evidence synthesis';
COMMENT ON COLUMN public.extracted_estimates.effect_summary IS 'Auto-generated natural-language summary for chatbot context';
COMMENT ON COLUMN public.extracted_estimates.extraction_method IS 'pipeline (automated), manual (human), llm_prose (from narrative)';

CREATE TRIGGER trigger_extracted_estimates_updated_at
    BEFORE UPDATE ON public.extracted_estimates
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE OR REPLACE VIEW public.study_effect_summary WITH (security_invoker = true) AS
SELECT
    study_id, authors, year, country, study_design,
    COUNT(*) AS total_effects,
    COUNT(DISTINCT outcome_category) AS outcome_categories,
    COUNT(*) FILTER (WHERE is_main_effect) AS main_effects,
    AVG(cohens_d) FILTER (WHERE cohens_d IS NOT NULL) AS avg_cohens_d,
    AVG(hedges_g) FILTER (WHERE hedges_g IS NOT NULL) AS avg_hedges_g,
    MIN(p_value) AS min_p_value,
    ARRAY_AGG(DISTINCT outcome_category) FILTER (WHERE outcome_category IS NOT NULL) AS outcome_categories_list
FROM public.extracted_estimates
GROUP BY study_id, authors, year, country, study_design;

CREATE OR REPLACE VIEW public.outcome_meta_analysis WITH (security_invoker = true) AS
SELECT
    outcome_category,
    COUNT(DISTINCT study_id) AS n_studies,
    COUNT(*) AS n_estimates,
    AVG(cohens_d) AS pooled_cohens_d,
    STDDEV(cohens_d) AS sd_cohens_d,
    AVG(hedges_g) AS pooled_hedges_g,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cohens_d) AS median_cohens_d
FROM public.extracted_estimates
WHERE cohens_d IS NOT NULL
GROUP BY outcome_category;

-- =============================================================================
-- Row Level Security
-- =============================================================================

ALTER TABLE public.rag_projects        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processing_jobs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zotero_connections  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_history        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_logs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_runs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.query_quality_logs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.extracted_estimates ENABLE ROW LEVEL SECURITY;

-- rag_projects
CREATE POLICY "Users can view own rag_projects" ON public.rag_projects
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY "Anyone can view public rag_projects" ON public.rag_projects
    FOR SELECT TO anon, authenticated USING (is_public = true);
CREATE POLICY "Users can insert own rag_projects" ON public.rag_projects
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can update own rag_projects" ON public.rag_projects
    FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can delete own rag_projects" ON public.rag_projects
    FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

-- documents
CREATE POLICY "Users can view documents in own projects" ON public.documents
    FOR SELECT TO authenticated
    USING (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));
CREATE POLICY "Users can insert documents in own projects" ON public.documents
    FOR INSERT TO authenticated
    WITH CHECK (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));
CREATE POLICY "Users can update documents in own projects" ON public.documents
    FOR UPDATE TO authenticated
    USING (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));
CREATE POLICY "Users can delete documents in own projects" ON public.documents
    FOR DELETE TO authenticated
    USING (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));

-- processing_jobs
CREATE POLICY "Users can view jobs in own projects" ON public.processing_jobs
    FOR SELECT TO authenticated
    USING (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));
CREATE POLICY "Users can insert jobs in own projects" ON public.processing_jobs
    FOR INSERT TO authenticated
    WITH CHECK (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));

-- zotero_connections
CREATE POLICY "Users can manage own project zotero connections" ON public.zotero_connections
    FOR ALL TO authenticated
    USING (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())))
    WITH CHECK (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));

-- chat_history (signed-in users see their own rows; anonymous rows are reachable only via the backend)
CREATE POLICY "Users can view own chat_history" ON public.chat_history
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can insert own chat_history" ON public.chat_history
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can delete own chat_history" ON public.chat_history
    FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

-- usage_logs
CREATE POLICY "Users can view their own usage" ON public.usage_logs
    FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()));

-- extracted_estimates
CREATE POLICY "Users can view estimates in own projects" ON public.extracted_estimates
    FOR SELECT TO authenticated
    USING (rag_project_id IS NULL
           OR rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));
CREATE POLICY "Users can modify estimates in own projects" ON public.extracted_estimates
    FOR ALL TO authenticated
    USING (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())))
    WITH CHECK (rag_project_id IN (SELECT id FROM public.rag_projects WHERE user_id = (SELECT auth.uid())));

-- evaluation_runs and query_quality_logs: no policies for anon/authenticated, so only the
-- backend's service_role (which bypasses RLS) can read or write them.
