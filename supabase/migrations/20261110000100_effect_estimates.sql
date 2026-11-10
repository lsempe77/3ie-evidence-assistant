-- Effect estimates extracted from studies' results tables (roadmap N6, 10 November 2026).
--
-- One row per reported estimate: outcome, treatment arm, subgroup, the number and its
-- precision, where it sits in the paper, and the verbatim cell. Step 1 imports the
-- estimates the 8-week graduation review extracted (pipelines/8w-sr/OM_QEX, source
-- 'om_qex_2025'); step 2 adds the app's own extraction from the Docling output.

CREATE TABLE IF NOT EXISTS public.effect_estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,
    doc_key TEXT NOT NULL,
    source TEXT NOT NULL,                 -- 'om_qex_2025', later the app's own extraction
    study_ref TEXT,                       -- e.g. the EPPI-Reviewer ID
    table_number TEXT,
    outcome_name TEXT NOT NULL,
    outcome_description TEXT,
    treatment_arm TEXT,
    subgroup TEXT,
    effect_size DOUBLE PRECISION,
    standard_error DOUBLE PRECISION,
    p_value DOUBLE PRECISION,
    p_text TEXT,                          -- as reported when not a number ("p < 0.01", "***")
    ci_text TEXT,
    sample_size INTEGER,
    literal_text TEXT,                    -- the cell as printed
    text_position TEXT,                   -- "Table 8, Row 'Sickness', Column '2005 over 2002'"
    page INTEGER,
    extraction_method TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_effect_estimates_project_doc ON public.effect_estimates(rag_project_id, doc_key);
CREATE INDEX IF NOT EXISTS idx_effect_estimates_source ON public.effect_estimates(rag_project_id, source);

COMMENT ON TABLE public.effect_estimates IS
    'Estimates extracted from results tables, one row per reported effect, with source and location';

-- Server-side only (the API uses the service role).
ALTER TABLE public.effect_estimates ENABLE ROW LEVEL SECURITY;
