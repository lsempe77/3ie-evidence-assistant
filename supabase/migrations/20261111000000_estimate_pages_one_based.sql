-- Pages of the app's own estimates count from 1, as chunk pages do (11 November 2026).
-- The tables_v1 extraction stored Docling's page_idx, which counts from 0, so every page
-- pointed one page early. Applied once (recorded in _schema_migrations); the extractor
-- now adds 1 itself.

UPDATE public.effect_estimates SET page = page + 1 WHERE source = 'tables_v1' AND page IS NOT NULL;
