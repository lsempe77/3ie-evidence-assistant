-- Study facts: one structured record per document (roadmap N6 step 3, 10 November 2026).
--
-- Programme, countries, whether women are the main recipients, components, cost per
-- beneficiary, transfer value, benefit-cost ratios and headline effects, each figure with
-- its verbatim quote and page (src/extraction/study_facts.py). The answer step computes
-- medians and group comparisons from these records in code.

CREATE TABLE IF NOT EXISTS public.study_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rag_project_id UUID NOT NULL REFERENCES public.rag_projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,
    doc_key TEXT NOT NULL,
    facts JSONB NOT NULL,
    model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (rag_project_id, doc_key)
);

COMMENT ON TABLE public.study_facts IS
    'One structured record per document, every figure with a verbatim quote and page';

-- Server-side only (the API uses the service role).
ALTER TABLE public.study_facts ENABLE ROW LEVEL SECURITY;
