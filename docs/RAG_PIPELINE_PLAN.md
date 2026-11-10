# RAG pipeline plan: what to copy, what to improve

**Date:** 7 November 2026
**Status:** direction agreed on 7 November 2026: **replace** the Nouswise-hosted DevChat and become the
state-of-the-art evidence RAG for international development
**Scope:** every stage of the 3ie Evidence Assistant's retrieval-augmented generation (RAG) pipeline. Each stage is
compared with 3ie's Nouswise-hosted DevChat and with state-of-the-art scholarly RAG systems. The plan ends with
priorities.

---

## 1. Why now

3ie already runs a public "DevChat" on Nouswise (`3ie.nouswise.com`). It answers questions over the Development
Evidence Portal (DEP), about 18,000 impact evaluations and 1,500 systematic reviews. Its homepage advertises six
features:

| Nouswise DevChat feature | What it means in practice |
| --- | --- |
| Intellectual humility | Refuses to answer when the library does not support an answer |
| Multilingual | Ask and read answers in any language |
| Verifiable answers | Line-by-line citations, several per sentence |
| Curated library | Answers come only from the 18,000 curated DEP studies |
| Memory | Short-term (conversation) and long-term (user) memory |
| Writing assistant | Drafts text from the answers without leaving the tool |

The shared conversation link we were given (`/c/6aef…`) returns 404 without signing in, so this plan is based on
the public homepage and third-party descriptions of Nouswise, not on hands-on use.

**Decision (7 November 2026): this app replaces the Nouswise DevChat.** That changes the plan in four ways:

1. **The app is corpus-agnostic, and this plan is about the app.** It must work as well for a DEP-sized library
   (about 19,500 studies and reviews, open to everyone) as for a team's private collection of 50 PDFs. Which data
   goes in, and the rights to it, is a separate workstream. Section 5 only uses the DEP to size the app.
2. **Matching Nouswise is the floor, not the goal.** Every Nouswise feature above has to be present before the
   switch-over. Being state of the art means doing measurably better on development-evidence questions.
3. **"State of the art" must be shown, not claimed.** That needs a public benchmark for this field (section 4)
   and a side-by-side comparison with Nouswise and general deep-research tools on it.
4. **It becomes a public service.** Scale, reliability, cost per answer, accessibility and data rights move up
   the list.

The app's three advantages carry over and become the reasons to switch: **quantitative** answers from extracted
effect sizes, **study-level** evidence reasoning (design, context, quality), and **measured** accuracy against
human-coded keys.

---

## 2. Reference systems

| System | Type | What is worth copying |
| --- | --- | --- |
| Nouswise DevChat (3ie) | Commercial, DEP corpus | Refusal when evidence is thin, multilingual, sentence-level citations, memory, drafting |
| OpenScholar (Ai2, *Nature* Feb 2026) | Open research system, 45M papers | Self-feedback loop: draft, critique, retrieve more, revise. Citation accuracy on par with human experts, where GPT-4o fabricated 78–90% of citations |
| Ai2 ScholarQA | Open source | Organised, sectioned reports. Quotes extracted first, then synthesised, with every claim attributed |
| PaperQA2 (FutureHouse) | Open source agent | Paper-level search, then per-chunk relevance summaries ("RCS") before answering. Matches experts on its benchmarks |
| Elicit | Commercial | Structured extraction tables across many papers, systematic-review workflow |
| Consensus | Commercial | "Consensus Meter": the share of studies that support or contradict a claim |
| Undermind | Commercial agent | Iterative search for 5–10 minutes until coverage is good |
| NotebookLM-style tools | Commercial | Source-grounded chat over a user's own uploads, audio and visual summaries |

Most claims about the commercial tools come from vendor pages and third-party reviews. OpenScholar's figures come
from its own benchmark (ScholarQABench). Every borrowed technique therefore goes through our own evaluation (stage 8)
before it ships.

---

## 3. The pipeline, stage by stage

Each stage lists where the app is today, what the reference systems do, and what to build. Effort is a rough
estimate in days for one developer.

### Stage 0. Corpus and ingestion

- **Today:** user uploads, Zotero sync and bibliography import. MinerU on Modal, eight-step table clean-up,
  OpenAlex and Crossref metadata, study-design classification, effect-size extraction.
- **References:** Nouswise and DevChat use a fixed curated corpus. OpenScholar uses 45 million open-access papers.
- **Build:**
  - **DEP ingestion** (core, see sections 5 and 6): all DEP records as the shared public library, staged from
    metadata and abstracts to full text. Teams can still add their own PDFs in private projects.
  - **Parser union** (TVET T4, 5 d): Docling ∪ MinerU recalled 0.955 of tables in the TVET bake-off.
  - **Study cards** (2 d): one record per study (title, design, country, population, outcomes, sample size, risk
    of bias where known) generated once at ingestion and reused by every later stage.

### Stage 1. Indexing

- **Today:** parent-child chunks with contextual prefixes, Cohere `embed-v4.0`, Supabase pgvector (HNSW) plus
  English full-text, fused with RRF in `hybrid_search()`.
- **References:** contextual retrieval is now standard. Late chunking shows small gains on long documents (about 3%
  relative to naive chunking in one April 2026 benchmark). Table-aware chunking matters for results tables.
- **Build:**
  - **Table chunks** (2 d): index each results table as its own chunk with caption and notes, linked to its
    extracted estimates, so quantitative questions retrieve tables, not prose around them.
  - **Study-level vectors** (1 d): embed each study card, enabling paper-first retrieval (stage 3).
  - **Multilingual full-text** (1 d): the keyword index is English-only today. Add a `simple` configuration for
    non-English documents.

### Stage 2. Query understanding

- **Today:** query classification, filter extraction (year, sector, population), decomposition, step-back.
  HyDE exists but is off.
- **References:** Nouswise answers in the user's language. Deep-research systems route simple questions to a fast
  path and hard ones to an agent.
- **Build:**
  - **Language handling** (1 d): detect the language, translate the query to English for retrieval, answer in the
    user's language. Cheap, and closes the most visible gap with Nouswise.
  - **Router** (2 d): four routes. *Factual lookup* (fast path), *synthesis* (current pipeline), *quantitative*
    (stage 3 SQL tool), *deep research* (stage 3 agent). Each route has its own cost cap.
  - **Clarifying questions** (1 d): `query_clarifier.py` exists. Use it when the question names no population,
    intervention or outcome.

### Stage 3. Retrieval

- **Today:** single-pass hybrid search, multi-query RAG-Fusion, decomposition, MMR.
- **References:** PaperQA2 and Ai2 ScholarQA search for papers first, then passages inside them. Undermind and
  OpenScholar iterate until coverage is good.
- **Build:**
  - **Paper-first retrieval** (3 d): rank study cards, take the top 20–40 studies, then search passages only inside
    them. Stops one long report from crowding out other studies.
  - **Quantitative tool** (3 d): for quantitative questions, query `extracted_estimates` in SQL (filters on
    outcome, design, country) and return effect sizes with their table and page. **Nouswise cannot do this.**
  - **Deep-research mode** (5 d, roadmap S6): plan, search, read, find gaps, search again. Hard caps on rounds
    and spend.
  - **Citation-graph expansion** (3 d, later): add highly cited references of the top studies, reusing the TVET
    forward-citation pipeline.

### Stage 4. Reranking and evidence selection

- **Today:** Cohere `rerank-v3.5`, MMR, lost-in-the-middle ordering.
- **References:** Rerank 4 (Dec 2025). PaperQA2's relevance summaries: a small model writes a one-paragraph,
  question-specific summary of each candidate and scores it, and only high scorers reach the answer model.
- **Build:**
  - **Rerank 4** (0.5 d, roadmap S2).
  - **Relevance summaries** (2 d): replace raw chunks with scored, question-specific summaries that keep pointers
    to the exact passages. Fewer tokens, less noise, and the material for sentence-level citations.
  - **Per-study cap and design weighting** (1 d): at most N passages per study, and a visible tag for study
    design (RCT, quasi-experimental, qualitative).

### Stage 5. Synthesis

- **Today:** two-pass Claim Ledger (extract claims, bind to sources), inline `[Author, Year, p.X]` citations.
- **References:** Nouswise cites every line, often several times. OpenScholar drafts, critiques its own draft,
  retrieves for the gaps and revises. Ai2 ScholarQA writes sectioned reports. Consensus shows agreement across
  studies.
- **Build:**
  - **Sentence-level citations** (2 d): every sentence carries at least one citation to a quoted passage. The
    Claim Ledger already holds the claim-to-source links, so this is mostly prompt and rendering work.
  - **Refusal threshold** (1 d, roadmap item "explicit refusal"): if no passage clears a relevance threshold, say so, list
    the closest studies and stop.
  - **Evidence-strength wording** (2 d): phrase each finding by number and design of supporting studies ("three
    RCTs in two countries found…"), not by confident prose.
  - **Consensus summary** (3 d, roadmap item): per claim, supporting, mixed and contradicting studies, shown as a
    bar.
  - **Self-feedback pass** (3 d): one critique-and-revise round on synthesis and deep-research routes only.

### Stage 6. Verification

- **Today:** MiniCheck post-hoc natural-language inference.
- **References:** OpenScholar's feedback loop. FRANQ and HHEM for faithfulness. Two-model agreement as a cheap
  confidence signal.
- **Build:**
  - **Per-sentence check** (2 d): run the check on each sentence against its cited passages and drop or flag
    unsupported sentences before display.
  - **Contradiction flags** (2 d, Critical Gap #6): flag when cited studies disagree, and say so in the answer.

### Stage 7. Presentation and workflow

- **Today:** chat, PDF viewer with highlighted citations, Evidence Panel, exports (BibTeX, RIS, CSV), per-project
  prompts.
- **References:** Nouswise has memory and a writing assistant. Elicit has extraction tables. NotebookLM has
  summaries of whole collections.
- **Build:**
  - **Evidence table view** (2 d): answers to quantitative questions render as a table (study, design, country,
    outcome, effect, CI, page link), exportable to CSV.
  - **Project memory** (2 d): save a project's decisions and preferred definitions (for example "ultra-poor means
    …") and feed them into prompts. Long-term personal memory can wait.
  - **Draft mode** (2 d): turn a saved answer into a draft section of a brief or review, keeping citations.

### Stage 8. Evaluation and operations

- **Today:** a faithfulness baseline of 66.5% of claims supported, measured on only 5 queries in January 2026.
  Langfuse tracing. No human-keyed accuracy.
- **References:** ScholarQABench, 3ie's own credibility framework for DevChat (does the answer address the
  question, do facts match the cited sources, how gaps and conflicts are handled).
- **Build:**
  - **Evaluation set** (3 d): 60–100 questions on the graduation corpus, scored on 3ie's three credibility
    criteria plus citation precision and recall. Reuse the TVET matcher for the quantitative questions.
  - **Regression gate** (1 d): run the set before each prompt, model or pipeline change, and block a merge if
    scores drop.
  - **Cost and latency per route** (1 d): Langfuse dashboards by route, so deep research stays affordable.
  - **Side-by-side with Nouswise** (1 d): run the same questions through both and compare on the same rubric. This
    tells 3ie where each tool is stronger.

---

## 4. Proving "state of the art": a development-evidence benchmark

No public benchmark covers development-evidence questions. Building one is the fastest way to show that this app
is better than Nouswise, and it is publishable.

- **Gold answers already exist.** 3ie's roughly 1,500 systematic reviews each state a question, the studies they
  included and their conclusions. Turned into benchmark items, they give:
  - **retrieval recall:** how many of the review's included studies the app finds for the review's question,
  - **answer agreement:** whether the app's conclusion matches the review's, judged by experts on a sample,
  - **quantitative accuracy:** whether effect sizes the app reports match the review's extraction tables (the TVET
    matcher already does this comparison).
- **Question mix:** 300–500 items, covering factual lookups, "what works" synthesis, quantitative questions,
  questions the evidence cannot answer (refusal must be right), and non-English questions.
- **Scoring:** 3ie's existing credibility criteria (addresses the question, facts match sources, handles gaps and
  conflicts), plus citation precision and recall, refusal accuracy, latency and cost per answer.
- **Comparators:** Nouswise DevChat, a general deep-research tool, and a plain LLM with no retrieval.
- **Guarding against overfitting:** keep a held-out set of reviews that is never used while tuning.

**Target for the switch-over:** at least parity with Nouswise on every criterion, and clearly better on retrieval
recall, quantitative accuracy and refusal accuracy.

---

## 5. Sizing the app for a DEP-scale library

The app has to handle at least this load. Rough estimates, to confirm with a 500-study pilot:

| Item | Estimate |
| --- | --- |
| Documents | About 19,500 (18,000 impact evaluations, 1,500 reviews) |
| Chunks | About 2 million at the current chunk size |
| Vector storage | About 6 GB of `halfvec` plus a similar-sized index: needs a larger Supabase compute size than Micro (roughly $60–110 a month instead of $10) |
| PDF parsing (MinerU on T4 GPUs) | About 450 GPU-hours, roughly $250–300 one-off |
| Contextual prefixes (current method) | About 5 billion input tokens, roughly $700 one-off with `gpt-4o-mini`. A cheaper scheme (prefix per section, or document summary cached once) could cut this by a factor of five or more |
| Embeddings | About 750 million tokens, roughly $90 one-off |

A staged approach keeps the first bill small:

1. **Metadata and abstracts for all ~19,500 records** (cheap, days). The study-card layer works across the whole
   DEP on day one.
2. **Full text for the open-access subset**, processed in batches, measured against the benchmark after each batch.
3. **Full text for the rest**, only where 3ie has the right to store and process it (decision 2 below).

---

## 5b. Additions after the November 2026 review

A check of 2026 RAG trends against this plan (10 November 2026), read alongside the benchmark: the 2024
query-rewriting chain scored 0.29, and reading every relevant study scored 0.49. Gains came from retrieval
coverage, reading and an honest synthesis prompt more than from orchestration. Five items were missing:

1. **Count programmes as well as papers** (stage 5). Several papers often evaluate one programme, so a
   count of papers overstates how independent the evidence is. Roadmap N1b.
2. **A bounded sufficiency check** (stages 3 and 6). Search again, once, when few studies are relevant.
   Never fall back to the open web. Roadmap N9.
3. **An MCP server** (stage 7). Expose collections to Claude, Copilot and other clients with the same
   citations and access rules. Roadmap N10.
4. **Write back validated data, never answers** (stage 0). Reviewed metadata and human-checked effect sizes
   feed the collection. Generated answers are never stored as sources. Roadmap N11.
5. **Figure descriptions** (stage 1). Captions plus a model-written description for charts such as forest
   plots. Roadmap N12.

For GraphRAG, the useful graph here is a structured evidence base (programme, studies, countries,
components, outcomes, effect sizes), not entity graphs extracted by a model. It grows out of the study
cards and the quantitative layer in Phase B.

## 6. Priorities

**Phase 0, foundations (about 3 weeks, partly in parallel).**
DEP metadata and abstracts for all records, a 500-study full-text pilot, the benchmark (first 100 items), the
model upgrade (roadmap S1), Rerank 4.
*Outcome:* the whole DEP is searchable at study level, and quality is measured from the start.

**Phase A, Nouswise parity (about 2 weeks).**
An end-to-end audit of every screen and journey (sign-up, projects, upload, processing, chat, sharing). Broken
flows get fixed as they are found. The first one, "Research Chat" sending signed-in users to the sign-in page,
also revealed that owners could not chat with their private projects while anyone could query them. Then language handling,
refusal threshold, sentence-level citations, memory for a conversation, the regression gate.
*Outcome:* every feature Nouswise advertises, with numbers on the benchmark.

**Phase B, the reasons to switch (about 3 weeks).**
Study cards, paper-first retrieval, table chunks, the quantitative SQL tool, the evidence table view,
evidence-strength wording, relevance summaries.
*Outcome:* answers with effect sizes, study designs, contexts and page-level sources.

**Phase C, best in class (about 3 weeks).**
Router with a deep-research mode, self-feedback pass, consensus summary, per-sentence verification,
contradiction flags, long-term memory, draft mode, citation-graph expansion.

**Phase D, public service (about 2 weeks, before switch-over).**
Load testing, rate limits and abuse protection, uptime monitoring, accessibility review, privacy notice,
custom email sender for sign-ups, an organisation-owned account for every service.

**Switch-over:** when the benchmark target in section 4 is met, run both tools side by side for a few weeks with
real users, then redirect the Nouswise DevChat link.

Within each phase, ship one item at a time behind the regression gate.

---

## 7. Decisions needed

1. ~~Positioning against Nouswise~~ **Decided:** replace it.
2. **DEP access and rights:** is there an export or API for DEP records, and may 3ie store and process the full
   texts (including paywalled ones) in this app? This sets how much of the corpus can be full text.
3. **Budget:** the one-off corpus cost (roughly $1,000–1,500 at current prices, less with the cheaper prefix
   scheme) and the monthly running cost, including model calls per answer at public traffic levels.
4. **Benchmark ownership:** who at 3ie reviews the benchmark items and expert-judges the answer sample.
5. **Switch-over owner and date:** who decides that the target is met, and the Nouswise contract end date.

---

## Sources

- 3ie DevChat on Nouswise: <https://3ie.nouswise.com/homepage>
- 3ie, "DevChat: Development evidence chatbot": <https://3ieimpact.org/our-work/devchat-development-evidence-chatbot-making-evidence-accessible>
- 3ie, "Learning on the go: building and testing our Gen AI-based evidence assistant": <https://3ieimpact.org/blogs/learning-go-building-and-testing-our-gen-ai-based-evidence-assistant>
- OpenScholar in *Nature* (coverage): <https://www.infodocket.com/2026/02/04/research-paper-synthesizing-scientific-literature-with-retrieval-augmented-language-models/>, preprint <https://arxiv.org/abs/2411.14199v1>
- Ai2 Scholar QA: <https://arxiv.deeppaper.ai/papers/2504.10861v1>
- Elicit, Consensus and Undermind compared: <https://theaiagentindex.com/compare/undermind-vs-elicit>, <https://toolradar.com/compare/elicit-vs-consensus>
- Nouswise feature listings: <https://theresanaiforthat.com/ai/nouswise>, <https://www.kdnuggets.com/exploring-notebooklm-alternatives>
- RAG practice in 2026: <https://dev.to/young_gao/rag-is-not-dead-advanced-retrieval-patterns-that-actually-work-in-2026-2gbo>, <https://fast.io/resources/best-chunking-strategies-for-rag/>
