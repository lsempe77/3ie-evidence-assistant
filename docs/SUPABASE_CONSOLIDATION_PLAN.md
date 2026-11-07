# Supabase consolidation plan

**Decision (7 November 2026):** stay with Supabase and make it the single data layer. Qdrant is removed.
Moving files from Cloudflare R2 to Supabase Storage is optional and decided after Phase 5.

**Target stack:** Vercel (frontend) + Railway (FastAPI) + Supabase Pro (Postgres with pgvector, Auth, Storage) +
Modal (GPU parsing only) + model APIs (OpenRouter, Cohere, Langfuse).

---

## Phase 0. Fresh start (decided 7 November 2026)

Both old data stores are gone. Neither old Supabase project (`kpgooeknvgzivrpekfqr`, nor the one in `.env`) exists
in the account any more, and the Qdrant vectors have disappeared. **The owner chose to discard all previous data**:
users, projects, chat history, extracted estimates and vectors. Only the files in R2 survive, and they are reused as
seed data to avoid paying for parsing again.

1. **Owner: create a new Supabase project** named `3ie-evidence-assistant`.
   - Put it in a **new organisation on the Pro plan**, not in the organisation that holds the four existing projects.
     Supabase bills compute per project across the whole organisation, with one $10 credit per organisation. Upgrading
     the existing organisation would charge for all five projects, about $65 a month instead of $25.
   - Region: the one closest to the Railway service.
2. **Owner: copy four values into `.env`:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   (Settings → API) and `SUPABASE_DB_URL` (Settings → Database → connection string, session pooler).
3. **Build the schema** from a single baseline migration that combines `supabase/schema.sql`,
   `scripts/migrations/*.sql` and `supabase/migrations/*.sql` in order, plus Phase 1 below. Apply it with `psycopg2`.
   - **Check:** all eight tables the code uses exist (`rag_projects`, `documents`, `processing_jobs`, `usage_logs`,
     `evaluation_runs`, `query_quality_logs`, `chat_history`, `zotero_connections`), plus `extracted_estimates` and
     `chunks`. Row-level security is on.
4. **Point every service at the new project:** Modal secret `SUPABASE`, Railway variables, Vercel
   `NEXT_PUBLIC_SUPABASE_*` variables, and Supabase Auth's Site URL and redirect list.
5. **Remove Qdrant:** delete the Qdrant Cloud cluster and the `qdrant-credentials` Modal secret, once Phase 2 no
   longer needs them.

---

## Phase 1. Schema

**Done 7 November 2026** on branch `feat/supabase-fresh-start`, applied to project `jyqzexzyemypdtfyfmhp`:

- `supabase/migrations/20261107000000_baseline.sql` consolidates the legacy schema (old files moved to
  `supabase/legacy/`). Views now respect row-level security, service-role policies no longer depend on the JWT role
  claim, and anonymous chat history is no longer readable through the public API.
- `supabase/migrations/20261107000100_chunks_pgvector.sql` adds `chunks` and `hybrid_search()`.
- `scripts/db_migrate.py` applies pending migrations and records them in `public._schema_migrations`.
- Checked: 10 application tables, all with row-level security on. Six views use `security_invoker`. pgvector 0.8.2,
  pg_trgm and pgcrypto are installed. A rolled-back smoke test inserted a project and three chunks, and
  `hybrid_search()` ranked them as expected.

The original design notes follow.

One new migration, `supabase/migrations/<date>_chunks_pgvector.sql`:

- `create extension if not exists vector;`
- Table `chunks`: `id`, `project_id` (FK to `rag_projects`), `document_id`, `chunk_index`, `parent_id`, `text`,
  `context_prefix`, `page_start`, `page_end`, `metadata jsonb`, `embedding halfvec(1536)`, and
  `fts tsvector generated always as (to_tsvector('english', coalesce(context_prefix, '') || ' ' || text)) stored`
- Indexes: HNSW on `embedding` (`halfvec_cosine_ops`), GIN on `fts`, B-tree on `(project_id, document_id)`
- Row-level security: the same ownership rule `rag_projects` uses
- SQL function `hybrid_search(project_id, query_embedding, query_text, match_count, rrf_k)` that fuses vector and
  full-text rankings with reciprocal rank fusion inside Postgres (the pattern Supabase documents for hybrid search)

**Size:** a 1,536-dimension `halfvec` takes about 3 KB, so 100,000 chunks need about 300 MB plus the index. That
fits within Pro's 8 GB. The HNSW index should sit in memory, which may need the Small compute size (about $5/month
more after Pro's compute credit). Decide once the real chunk count is known.

---

## Phase 2. Code

**Progress (7 November 2026), branch `feat/supabase-fresh-start`:**

- **2a, done:** `src/vectorstore/chunk_store.py`, `HybridRetriever` and `ChunkIndexer` on Supabase; search
  functions with filters (`20261107000200_chunk_functions.sql`).
- **2b, done:** API routes (`rags.py`, admin collection, documents, metadata, jobs, storage, status),
  `api/vector_status.py`, and a `DEFAULT_PROJECT_ID` setting for the legacy single-project endpoints. A live
  smoke test created a project through the API, stored chunks, searched them (vector, keyword and legacy names),
  reset them and deleted the project. `api/routes/health.py` is outside this session's edit permissions, so it
  keeps importing a small shim (`api/qdrant_status.py`) that maps the old names to the new module.
- **2c, done:** Modal (`modal_lib/chunks.py`; `embed_and_index` writes to Supabase; app renamed
  `evidence-assistant-mineru`; `src/` mounted into the image), scripts (Qdrant-only maintenance scripts moved to
  `scripts/archive/`), frontend wording and response fields (`chunk_store_reachable`, `live_chunk_count`,
  `chunk_status_message`), `qdrant-client` and Qdrant settings removed, and `rag_projects.qdrant_collection`
  dropped (`20261107000300_drop_qdrant_collection.sql`). Every module imports with `qdrant_client` blocked.


Twelve files import the Qdrant client:

| Area | Files |
| ---- | ----- |
| Retrieval | `src/retrieval/hybrid_retriever.py`, `src/retrieval/query_processor.py` |
| Indexing | `src/ingestion/indexer.py`, `src/ingestion/study_design_classifier.py` |
| API | `api/routes/rags.py`, `api/routes/admin/collection.py`, `api/routes/admin/metadata.py`, `api/qdrant_status.py` |
| Modal | `infrastructure/modal_lib/embedding.py`, `orchestration.py`, `processing.py` |
| Utilities | `src/utils/logging.py` |

- Replace `HybridRetriever` and `QdrantIndexer` with Postgres implementations behind the **same interfaces**, so the
  agent, MMR, lost-in-the-middle ordering, multi-query fusion and Cohere reranking stay unchanged
- Per-project collections (`rag_<project_id>`) become a `project_id` filter on one table. The
  `rag_projects.qdrant_collection` column is retired
- Qdrant's sparse BM25-style vectors are replaced by Postgres full-text ranking. This is the one change that can move
  retrieval quality, so Phase 4 measures it
- Modal's indexing writes to Postgres through the existing `SUPABASE` secret
- Admin status pages report Postgres counts instead of Qdrant collection info

---

## Phase 3. Data

**Update 7 November 2026:** the Qdrant vectors are gone, so Option A is no longer available. Option B applies.

- ~~**Option A: export from Qdrant.**~~ Not possible.
- **Option B: rebuild from R2.** R2 is intact. What it holds (inventory of 7 November 2026):

  | Project | PDFs | Parsed (Markdown) | Last upload |
  | ------- | ---- | ----------------- | ----------- |
  | `0816e8d3…` (graduation corpus) | 97 | 97 (10.2 MB) | 27 Jan 2026 |
  | `bc8ddfa1…` | 151 | 0 | 4 Jan 2026 |

  **Rough cost at today's model settings**, to confirm before running:
  - Graduation corpus: about 8,000 child chunks. Contextual prefixes with `gpt-4o-mini` take about 19 million
    input tokens (each call sends up to 8,000 characters of the document), roughly $3–4. Cohere embeddings take
    about 3 million tokens, under $1.
  - Project `bc8ddfa1…`: its 151 PDFs were never parsed, or the output was not kept. It needs MinerU on a Modal T4
    first, roughly 5 GPU-hours (about $3), then the same prefix and embedding steps (a few dollars).
  - **Total: roughly $10–15.** That is several times more if the prefix model is upgraded first (roadmap S1).

  **Get approval before running.**

**Check:** the chunk count per project matches Qdrant (Option A) or the document count in Supabase (Option B).

---

## Phase 4. Verify

- Qdrant is gone, so there is no old system to compare against. Instead, run 50–100 evaluation queries (roadmap
  item S5) on the graduation corpus with three settings: vector only, full-text only, and hybrid. Hybrid should beat
  both. Compare faithfulness with the January baseline (66.5%)
- Re-run the faithfulness evaluation on the new stack
- Check query latency with the index in memory

If hybrid does not beat vector-only, tune the full-text configuration or the fusion weights before going live.

---

## Phase 5. Cutover and decommission

1. Deploy the Postgres-backed code to Railway and Modal
2. Watch errors and latency for a week
3. **With approval:** delete the Qdrant cluster, and remove `qdrant-client`, the Qdrant secrets and environment variables

---

## Phase 6 (optional). R2 → Supabase Storage

Pro includes 100 GB of file storage. Moving PDFs and parser output there removes the R2 account, but saves little
money, because R2 has a free allowance and no egress fees. It needs changes to the presigned-URL code and to Modal's
file access. Decide after Phase 5.

---

## Effect on the rename plan

- **Step 3 (Qdrant alias): dropped.** There is no Qdrant to rename.
- **Step 4 (new R2 bucket):** replaced by Phase 6 if chosen. Otherwise it runs as planned.
- Steps 5–9 are unchanged.

---

## Effort and running cost

- **Effort:** Phases 1–4 take about 3–5 days. Phase 6 takes about 1 day.
- **Monthly cost after:** Supabase Pro $25 (plus about $5 if Small compute is needed), Railway Hobby from $5, Modal per
  use, model APIs per use. Vercel's free Hobby plan is restricted to non-commercial use, so check whether 3ie's use
  needs Vercel Pro ($20 per member per month).
