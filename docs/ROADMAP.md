# 3ie Evidence Assistant roadmap (formerly DevChat)

**Last Updated:** 11 November 2026

> This document tracks **future features** and priorities.  
> For current implementation status, see [SETUP_TRACKER.md](../SETUP_TRACKER.md).  
> For extraction pipeline details, see [extraction_pipeline/README.md](../extraction_pipeline/README.md).
>
> **Direction (7 November 2026):** this app will **replace** 3ie's Nouswise-hosted DevChat and aims to be the
> state-of-the-art evidence RAG for international development. The stage-by-stage plan, benchmark and phases are in
> [RAG_PIPELINE_PLAN.md](RAG_PIPELINE_PLAN.md), which takes precedence over older items below where they overlap.

---

## Upcoming Features

### Status on 11 November 2026

**What is live.** Answers come from the read-then-synthesise pipeline (`src/agents/study_synthesis.py`):

1. Study cards rank whole studies.
2. Haiku 5.5 reads every candidate study, with the effect estimates extracted from that study's tables.
3. Sonnet 5.5 writes the answer from the readings, plus figures computed across the collection from
   study facts.

Answers stream to a live progress view, and three follow-up questions arrive after the answer. Railway
serves the API from `main`, Vercel serves the frontend, and Modal processes uploads. Processing now also
builds study cards, extracts estimates and study facts, and regroups programmes.

**Benchmark** (graduation review brief, 20 questions, 49 gold claims, two judges):

| Date | Change | Claim score |
| --- | --- | --- |
| 9 Nov | Old pipeline (passage retrieval, one answer call) | 0.29 |
| 9 Nov | Read-then-synthesise, Haiku 5.5 | 0.47 to 0.50 |
| 10 Nov | Study cards and programme counting (N1, N1b) | 0.52 |
| 10 Nov | Sonnet 5.5 answers, baseline for the gate (N3) | 0.552 |
| 10 Nov | Estimates from tables in the reader (N6 step 2) | 0.559 |
| 11 Nov | Study facts and computed figures (N6 step 3) | 0.545 |

Single runs move by about 0.03, so the last three are level. The 7 pooled gold claims did not move with
N6. They rest on the review's own conversions (2024 dollars, a 20-year cost-benefit model) or on a
comparison the collection cannot support, so they are a weak target for tuning. N6 made the answers more
quantitative (estimates with tables and pages, medians, ranges, counts) without lowering the score.

**Cost.** About 4.5 US cents per question (Haiku reads, Sonnet answers). Processing adds about 3.5 cents
per document for estimates and study facts. One-off N6 runs on the graduation collection: $2.50 for
estimates and $0.89 for study facts.

**Collection data built on 10 and 11 November.** These are for the graduation collection.

- 20,465 grounded estimates from 90 of 97 documents (SE 78%, N 59%, page 100%).
- Study facts for all 97 documents: 93 evaluations of about 41 programmes in 29 countries.

#### Open issues

- The benchmark gate on pull requests skips itself until four repository secrets are added
  (`OPENROUTER_API_KEY`, `COHERE_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).
- The new Modal steps (estimates, study facts, programme groups) were checked for imports in the Modal
  image, but no real upload has gone through them yet.
- The answer model reasons for about 12 s before its first word. Test a lower reasoning effort on the
  benchmark.
- "Deeper answer" stays hidden until Opus 5.5 is benchmarked.
- On 10 November a same-day benchmark run overwrote the results file of the baseline run. The
  summary survives in `baseline.json`, and the full file only in OneDrive version history.
  `run_benchmark.py` now adds a time suffix instead.

**Suggested next steps, in order:** N6 follow-ups (an evidence table in the interface, costs in one price
year, a better women-as-recipients flag), N5 questions in other languages, N7 collection-page design,
then N9 to N12.

### ▶ Next up (after the model review, 10 November 2026)

> Since 9 November 2026 answers come from the "read every relevant study, then synthesise" pipeline with
> Claude Haiku 5.5 (0.49 of the graduation review's claims, against 0.29 before). Evidence and reasons:
> [MODEL_REVIEW_2026-11.md](MODEL_REVIEW_2026-11.md). Run the benchmark (`evaluation/run_benchmark.py`)
> before and after each item below.

1. **N1. Study-level retrieval** - done 10 Nov 2026: studies read per question 23 to 43, relevant 10 to 20, claim score 0.49 to 0.52, answers 26 to 39 s (`study_cards` table, `src/retrieval/study_cards.py`)
   - Broad questions read only 10 to 52 of the 86 included studies held, because passages are ranked one by
     one. Rank whole studies first (title, abstract, best passages), then fetch passages within each.
   - Target: most of the included studies read on broad questions, at no more than double today's cost.

   **N1b. Count programmes as well as papers** - done 10 Nov 2026 (reader names the programme, answers say "N studies of M programmes")
   - About 30 papers in the graduation collection evaluate BRAC's TUP programme alone, so "19 of 25
     studies" can overstate how independent the evidence is. The reader records which programme each study
     evaluates, and the answer counts programmes as well as papers ("19 studies of 11 programmes").

2. **N2. Something to watch while the answer is written** - done 10 Nov 2026 (`/api/query/stream`, `AnswerProgress`): steps, a live tally by direction and design, source cards as studies are read, streamed answer text. Open: the answer model reasons for about 12 s before its first word; test a lower reasoning effort on the benchmark
   - Today the screen shows skeleton lines for 20 to 40 seconds. The pipeline already knows a lot during
     that time, so show it as it happens:
     - **Progress in steps:** "Searching 97 documents", then "Found 52 candidate studies", then "Reading 18
       of 37", "12 relevant so far", "Writing the answer".
     - **A live tally:** a bar per direction (positive, null, mixed) that fills as each study is read, with
       the study designs underneath ("9 RCTs, 3 difference-in-differences").
     - **Studies arriving:** source cards appear in the Sources panel as they are read, each with its
       finding, so users can start checking before the answer lands.
     - Optional: a small map or country list of where the relevant studies took place.
   - Needs: server-sent events from `/api/query` (emit an event as each study reading completes in
     `src/agents/study_synthesis.py`), then stream the answer text itself.
   - Design: extends the loading state and the charts gap in [DESIGN.md](../DESIGN.md). Respect reduced
     motion, and announce progress politely to screen readers.

3. **N3. Confirm the default model** - done 10 Nov 2026: Haiku 5.5 reads, Sonnet 5.5 answers (0.56 vs 0.48 for Haiku answers on the same readings). Cheap open-weight readers lost about 0.03 to save 0.6 cents a question; Kimi K3.1 Pro matched Sonnet at the same price but missed a gap question. "Deeper answer" is hidden until a stronger model (Opus 5.5) is benchmarked. Benchmark gate done 10 Nov 2026: `evaluation/gate.py` and `.github/workflows/benchmark.yml` (quick 5-item check on pull requests, full check on demand, baseline in `evaluation/benchmark/baseline.json`; needs four repository secrets)
   - Repeat the three leading configurations twice more. Model differences (under 0.03) were within the
     noise of single runs.
   - Then make the benchmark a regression gate: run it before merging prompt, retrieval or model changes.

4. **N4. Follow-up questions** - done 10 Nov 2026 (one Haiku call after the answer, sent as a `suggestions` event, in the question's language)
   - The new pipeline dropped the "Related questions" suggestions. Bring them back as one cheap call after
     the answer is shown, so they do not add to the wait.

5. **N5. Questions in other languages** - 1 d
   - A Spanish question read only 2 studies against 3 Haku Wiñay documents held. Translate the question for
     retrieval (keep answering in the user's language), or retrieve with both versions.

6. **N6. Effect sizes and pooled comparisons** - steps 1 to 3 done 11 Nov 2026
   - Seven of the 49 gold claims need comparisons across studies, such as smaller income gains when women
     are the transfer recipients.
   - Step 1 (done, PR #21): the `effect_estimates` table, and 7,127 OM_QEX estimates for 77 studies imported
     as source `om_qex_2025`. Checked against the 20 hand-extracted estimates of three studies, OM_QEX found
     8 and had the right SE for 4 of them, so it is kept for reference and not used in answers.
   - Step 2 (done): our own extraction, `src/extraction/table_estimates.py`. One Haiku 5.5 call per Docling
     table copies the estimate, SE and p cells verbatim, tested code parses them to numbers (thousands
     separators, decimal commas, stars, intervals), and a row is kept only if its cells appear in the
     table. On the hand-extracted check it found 20 of 20 estimates with 19 of 20 SEs right. On the
     collection: 20,465 estimates from 90 of 97 documents (SE 78%, N 59%, stars or p 41%, page 100%) for
     about $2.50 (`scripts/extract_estimates.py`, then `scripts/embed_estimates.py`).
   - Each study's 12 estimates closest to the question go to the reader, which names the ones that
     answer it. Source cards list them as "Estimates from the paper" with the printed value,
     significance, N, table and page. The answer compares them across studies and never averages them.
   - Benchmark (full gate): 0.559 against the 0.552 baseline, so no loss, and within the run-to-run
     noise of about 0.03. The pooled claims did not move (grad-003 and grad-005 still 0). On the
     women-targeting question 9 of 12 relevant studies now cite their estimates, but the gold claim
     compares programmes that target women with those that do not, which needs step 3.
   - Known weaknesses: arm labels sometimes miss the column (three "Income, pooled panel" values from
     different specifications), a few values are column headers such as "0", and some N values are
     cluster counts. The lookup adds about 3 s, overlapped with the rerank.
   - New uploads: the Modal pipeline extracts estimates and study facts for each processed document
     (PR #23). Fixing its imports (PR #24) also restored the study-card rebuild on Modal, which had
     been failing quietly since study cards shipped.
   - Step 3 (done): study facts, one record per document (`src/extraction/study_facts.py`). One Haiku
     call reads the whole paper and fills a form: programme, countries, women as main recipients,
     components, total cost per beneficiary, transfer value, benefit-cost ratios and up to six
     headline effects as a percentage change. Every figure needs a quote found in the paper that
     contains it. One more call per collection groups name variants into programmes
     (`programme_groups.py`). Cost: $0.89 for 97 documents.
   - `src/agents/evidence_summary.py` computes figures across the collection in code, one figure per
     programme, and the answer uses them when the question asks for them: coverage (93 evaluations of
     about 41 programmes in 29 countries, against the review's 44 in 27), cost per beneficiary with
     nominal and PPP dollars kept apart (medians 389 and 2,839), transfer share of cost (median 34%),
     benefit-cost ratios (median 2.20), and headline effects grouped by women as main recipients.
   - Benchmark (full gate): 0.545 against the 0.552 baseline, within noise. The coverage and
     value-for-money answers now give counts and medians. The pooled gold claims stay hard because
     they use the review's own conversions (2024 dollars, a 20-year cost-benefit model) and a
     comparison of women-targeted programmes with others, where only one programme on the other side
     reports a percentage income change. The answers say so rather than guess.
   - Next: show the computed figures in the interface as an evidence table, convert costs to one price
     year, and improve the women-as-recipients flag (19 of 41 programmes do not say).

7. **N7. Design: collection pages** - 2-3 d
   - Documents and Settings next, following [DESIGN.md](../DESIGN.md). They hold most of the remaining
     technical wording.

8. **N9. Search again when the evidence is thin** - 1-2 d (bounded agentic step)
   - After reading, if few studies are relevant, reformulate the question (other terms, other language)
     and search once more. Hard limits on rounds and cost. Never fall back to the open web: answers stay
     within the collection. Searching DEP or OpenAlex can be an explicit option the user chooses.

9. **N10. The Evidence Assistant as an MCP server** - 1-2 d
   - Let 3ie staff query their collections from Claude, Copilot or other MCP clients, with the same
     citations and access rules. Later: connect DEP, OpenAlex and PubMed as live sources.

10. **N11. Write back validated data, never answers** - 2-3 d
    - Reviewed metadata, human-checked effect sizes and corrections feed back into the collection.
      Generated answers are never stored as sources, so they cannot contaminate the evidence base.

11. **N12. Describe figures** - 1-2 d
    - Docling extracts tables, but charts such as forest plots are not indexed. Add each figure's caption
      and a model-written description as a passage, with its page.

12. **N8. Housekeeping**
   - Remove the old claim-ledger path (`ANSWER_PIPELINE=agent`) and LlamaIndex once the new path has run
     for two weeks without problems.
   - Decommission the old `devchat-mineru` Modal app. Rename the R2 bucket (on hold).
   - Fix or remove the Sphinx docs workflow (GitHub Pages is not enabled). Check the unrelated
     Vercel project `giving-adaptation` (web) attached to this repository.

### 🚨 Critical Gaps (Must Fix Before Any Other Improvement)

These are foundational problems. Without solving them, every other "improvement" is unmeasurable guesswork.

1. **Golden Ground Truth Database** - 16h ⬅️ **#1 BLOCKER**
   - ❌ **No human-coded gold standard exists.** The "88% accuracy" is self-measured, not validated.
   - Need: Hand-extract effect sizes (coefficient, SE, p-value, sample size, outcome, treatment arm) for 10-15 representative studies (~150-300 rows)
   - Must cover: clean tables, messy OCR, multi-language, transposed formats, prose-only
   - Compare pipeline output row-by-row against human ground truth
   - Calculate real precision, recall, and F1 per field (coefficient, SE, outcome, etc.)
   - `data/master_UPG.csv` exists but is NOT a complete ground truth — it's a partial reference
   - **Output:** `data/ground_truth/` with verified CSVs per study + evaluation script
   - Files: New `evaluation/ground_truth_eval.py`
   - ➡️ **See TVET Transfer T1 and T2:** the scorer already exists, and the 8w-sr human extraction may already be the data

2. **Prompt Engineering Methodology** - 12h ⬅️ **#2 BLOCKER**
   - ❌ **All 9 prompts were written once and iterated by feel.** No systematic testing.
   - Need: Test prompt variants side-by-side on ground truth data
   - Ablation studies: Do few-shot examples help? How many? Which ones?
   - Temperature experiments: Does temp=0.0 vs 0.3 change accuracy?
   - Model comparison: Haiku vs Sonnet vs GPT-4o on same tables (cost-accuracy tradeoff)
   - Structured JSON mode vs free-text parsing comparison
   - **Output:** `evaluation/prompt_experiments/` with results per variant
   - Files: New `evaluation/prompt_ablation.py`
   - ➡️ **Do after TVET Transfer T3**, so prompts are tuned on the extraction design we keep

3. **Regression Testing Suite** - 8h
   - ❌ **No regression tests.** A prompt change can silently break 10 previously-working tables.
   - Need: Fixed test set of ~30 tables with expected outputs
   - Run after every prompt/parser change, fail if accuracy drops
   - Track: classification accuracy, coefficient match rate, SE match rate
   - **Output:** `tests/extraction/` with pytest fixtures from ground truth
   - Files: New `tests/extraction/test_regression.py`
   - ➡️ **See TVET Transfer T1:** wrap `match_outcomes.py` and `score_table_key.py` as the pytest assertions

4. **Coverage Measurement (Precision & Recall)** - 6h
   - ❌ **No idea what % of effect sizes the pipeline finds vs misses.**
   - Need: For ground truth studies, count how many real effects exist (from human coding)
   - Compare: pipeline-found vs human-coded → precision (% correct), recall (% found)
   - Break down by: table format, language, extraction method (table vs prose vs figure)
   - **Output:** Coverage report per study + aggregate metrics
   - Files: New `evaluation/coverage_analysis.py`
   - ➡️ **See TVET Transfer T1:** `match_outcomes.py` already reports per-study recall, precision and F1 with samples of unmatched rows

5. **Confidence Scores on Extractions** - 6h
   - ❌ **All outputs are point values with zero uncertainty.** Clean table extraction and blurry OCR guesses look identical.
   - Need: Score each extracted row on extraction confidence (0-1)
   - Factors: OCR quality, cell parsing ambiguity, LLM uncertainty, source type (table vs prose)
   - Flag low-confidence rows for human review priority
   - **Output:** `extraction_confidence` column in output CSVs
   - Files: `extraction_pipeline/pipeline.py`, all extractors

6. **Contradiction Resolution** - 4h
   - ❌ **When prose says "effect = 0.15" and table parser extracts 0.051, no logic flags this.**
   - Need: Cross-check table extraction vs prose extraction for same outcomes
   - Flag contradictions, prefer table values (more structured) but log disagreements
   - **Output:** `contradictions` column or separate log
   - Files: `extraction_pipeline/pipeline.py`

7. **Validation Against Published Meta-Analyses** - 8h
   - ❌ **Several programs (BRAC, GiveDirectly) have existing systematic reviews we could validate against.**
   - Need: Find published meta-analyses for overlapping studies
   - Compare our extracted effect sizes to published ones
   - Calculate: mean absolute error, correlation, systematic bias direction
   - **Output:** `evaluation/meta_analysis_comparison.py`

8. **User Feedback Loop** - 8h
   - ❌ **Researchers can't flag extraction errors in the frontend.** No corrections feed back.
   - Need: "Flag error" button on extracted estimates in Evidence Panel
   - Store corrections in Supabase `extraction_corrections` table
   - Use corrections to update ground truth and retrain/re-evaluate
   - Files: Frontend component + `api/routes/extraction.py` + migration

---

### 🔁 TVET Transfer (November 2026) ⬅️ **Start here**

> **Source:** `pipelines/TVET/`, outside this repo: a parser bake-off and outcome inventory on 78 TVET
> apprenticeship studies, October–November 2026. The document of record is
> `TVET/pipeline/BAKEOFF_AND_INVENTORY_REPORT.md`. Read `TVET/PROCESS_REPORT.md` before quoting any
> number, because several were corrected during that work.
> **Rule:** copy code in with a provenance note (source path plus SHA-256), as TVET did when it vendored
> OM_QEX. Never import across folders.

**Findings that change this roadmap:**

- On a 200-table human answer key (6 papers, three checkers, zero disagreements), Docling, bibr and
  MinerU each recall 0.94 of tables. MonkeyOCR recalls 0.075, keeps only 0.543 of decimals intact, and
  times out on papers over 24 pages. The Docling ∪ MinerU union recalls 0.955.
- Table counts are not a quality signal: the engines disagree by a factor of 3.6. The February 2026
  comparison in `evaluation/parser_comparison_results.json` relies on proxies of this kind.
- Restricting the extraction prompt to treatment-effect columns raised outcome F1 from 0.33 to 0.49,
  with recall holding at 0.82. Most of the remaining precision loss comes from the table filter keeping
  descriptive and balance tables.

1. **T1. Port the evaluation harness** - 6h ⬅️ unblocks Critical Gaps #1, #3 and #4
   - `TVET/pipeline/score_table_key.py`: precision and recall for table detection against a human key
   - `TVET/pipeline/match_outcomes.py`: matches rows on study, table and row label, then checks that the
     human point estimate appears among the machine row's numbers
   - `TVET/pipeline/bakeoff_metrics.py`: decimal recall against the PDF's own text layer, a fidelity
     measure that needs no human labels
   - `TVET/pipeline/make_ground_truth_sheet.py` + `pipeline/groundtruth/CHECKER_INSTRUCTIONS.md`: the
     process for building new keys
   - Adapt to the assistant's output schema (`extracted_estimates`, 28 columns, and
     `extraction_pipeline/outputs/full_corpus_for_validation.csv`)
   - **Output:** `evaluation/tvet/` with a `PROVENANCE.md`

2. **T2. Ground truth for the graduation corpus** - 4h to assess, more if hand-coding is needed
   - Check whether the 8w-sr human extraction in `data/8 week SR OM Combined.xlsx` and
     `data/8WR QEX Combined.xlsx` carries row-level locations (page, table, row label, point
     estimate). If it does, it is the ground truth for Critical Gap #1 at no new coding cost.
   - If it does not, apply T1's sheet generator and checker instructions to 10–15 studies
   - Also score the assistant's extractor on the 6 TVET pilot papers, which already have a key
     (`TVET/ground_truth_datasets/`), as a cross-domain check

3. **T3. Score both extraction designs against the same key** - 6h
   - Our `extraction_pipeline/` (rules + LLM over MinerU JSON) vs OM_QEX phases 1–3 (table
     discovery → filtering → extraction, as vendored in `TVET/pipeline/vendor/`)
   - Decide which design to keep **before** further prompt work (Critical Gap #2)

4. **T4. Add Docling to PDF processing and union it with MinerU** - 10h
   - Run Docling as a CPU function in `infrastructure/modal_lib/`
   - Port the deduplication from `TVET/pipeline/build_union_inventory.py` (study + normalised row
     label + set of numbers, with a `_sources` column)
   - Docling inflates text by about 1.5×, so chunking and deduplication must tolerate repeated
     content before indexing in Qdrant
   - Run experiments in a separate Modal app (TVET used `tvet-bakeoff`) so production
     `devchat-mineru`, Qdrant and R2 prefixes are never touched
   - Cost: about 8 s/page on CPU, so roughly 7 hours per 3,000 pages on one worker

5. **T5. Small fixes carried over from TVET** - 3h
   - Treatment-effect column filter in the extraction prompt (F1 0.33 → 0.49 in TVET)
   - Tighten table classification to exclude balance and cost-decomposition tables (TVET's open item,
     and its main source of lost precision)
   - Quote bibliography lines beginning `system:` before sending them to OpenRouter, which refuses them
     with HTTP 403 `system_prefix_spoofing` (check whether the assistant routes through OpenRouter)
   - Store the PDF page index alongside the printed folio. In one TVET study they differed by 2,384
   - Sanitise lone surrogates in parser Markdown:
     `md.encode("utf-8", "surrogatepass").decode("utf-8", "replace")`

6. **T6. Forward citations → Smart Citations** - later
   - TVET `fwdcite` pipeline (GROBID references → Crossref / OpenAlex / OpenCitations → citing works)
     on the TVET branch `forward-citation-refs`, not yet merged there
   - Feeds the Short-Term "Smart Citations" item
   - OpenAlex has been metered since 3 November 2026. Set `OPENALEX_API_KEY` before relying on it

**Operational notes from TVET:** the Modal profile `lsempe77` owns `devchat-mineru`. `3ieimpact` is
paused but is still the CLI default in `~/.modal.toml`. Use `python -m modal`, not `modal.exe`, which
exits silently on this machine.

---

### 🆕 SOTA Upgrade (November 2026)

> A scan of what changed between February and November 2026, run on 6 November 2026. Most sources are vendor
> pages and third-party blogs, so every swap below goes through the TVET Transfer harness (T1) on our own
> papers before it reaches production. Leaderboard ranks alone are not enough: TVET showed that general
> benchmarks miss the borderless tables in economics papers.

**Where the stack stands:**

| Component | In use | Current options (Nov 2026) | Gap |
| --------- | ------ | -------------------------- | --- |
| LLMs | `gpt-4o-mini`, `gpt-4o`, Claude 3.5 Haiku, `gemini-2.0-flash-exp`, `gemini-exp-1206` | GPT-5.x line, Claude 5 family (Haiku / Sonnet / Opus 5.5), Gemini 3.x (TVET ran Gemini 4 Argon through OpenRouter) | Large: every default is a 2024 model, and the experimental Gemini ids are likely retired |
| Reranker | Cohere `rerank-v3.5` | Cohere Rerank 4 Pro / Fast (Dec 2025, 32K context, multilingual), Voyage rerank-2.5, zerank-2 | Medium: Rerank 4 is a drop-in swap |
| Embeddings | Cohere `embed-v4.0` | Still Cohere's latest. Voyage-4-large, Gemini Embedding, Qwen3-Embedding-8B (open) | Small: benchmark before paying for a re-index |
| PDF parsing | MinerU ≥ 2.6 (pipeline backend) | MinerU 3.x with the MinerU2.5-Pro VLM (cross-page table merging), PaddleOCR-VL-1.6, Docling | Medium: see also TVET T4 |
| Vector DB | Qdrant, client-side BM25 sparse vectors | Qdrant 1.20 (Oct 2026): native BM25 on full-text indexes. 1.19: unified memory setting | Small: simplification, not quality |
| Faithfulness check | MiniCheck | RAGAS 0.4, Vectara HHEM / FaithJudge, LettuceDetect, FRANQ (ACL 2026 Findings) | Medium: the 5-query baseline is too small to steer by |
| Answer mode | Single-pass retrieve → Claim Ledger | Routed agentic "deep research" with a claim-evidence graph for complex questions | Medium: Claim Ledger is a good base |

1. **S1. Upgrade the LLM defaults** - done 9 Nov 2026, see [MODEL_REVIEW_2026-11.md](MODEL_REVIEW_2026-11.md)
   - Replace the defaults in `src/config/settings.py` and `api/routes/rags.py` (`DEFAULT_MODEL_CONFIG` and the
     model picker list), and remove retired experimental ids
   - Run each candidate on the T1/T2 ground truth for extraction and on an enlarged faithfulness set (S5)
     before switching. A January 2026 dentistry study found model choice changed extraction accuracy
     markedly and that cost did not track accuracy
   - Keep a fast/strong pair per provider. Record per-call cost in Langfuse to compare

2. **S2. Move to Cohere Rerank 4** - 2h
   - `rerank_model` in `src/config/settings.py`. Test Pro against Fast for the latency budget
   - Check Cohere's deprecation page for `rerank-v3.5`. Pinecone has served 3.5 requests with
     Rerank 4 Fast since 1 August 2026, a sign the old model is being retired
   - Optional: compare with Voyage rerank-2.5 on the same queries

3. **S3. Embedding benchmark** - 6h (replaces the Short-Term "Cohere vs Voyage 4" item)
   - Compare Cohere `embed-v4.0`, Voyage-4-large and Gemini Embedding on recall@k and NDCG for 50+ real queries
   - Re-index only if the gain is clear. A re-index rebuilds every vector and contextual prefix

4. **S4. Parser upgrade** - 8h, together with TVET T4
   - Upgrade to MinerU 3.x and test the VLM / hybrid backend. Check the custom Apache-2.0-based licence
     introduced in 3.1 before deploying
   - Score MinerU 3, Docling and PaddleOCR-VL with `score_table_key.py` and decimal recall, not table counts
   - Decide the union (TVET found Docling ∪ MinerU recalled 0.955 of tables)

5. **S5. Stronger faithfulness evaluation** - 8h
   - Grow the evaluation set from 5 queries to 50–100, covering comparisons, null results and out-of-corpus questions
   - Add a second judge next to MiniCheck (HHEM or RAGAS 0.4 faithfulness) and report agreement between them
   - Feeds the "Improve Faithfulness" item: tune against this set, not the 5-query baseline

6. **S6. Deep-research mode** - 20h (absorbs the Medium-Term "Agentic RAG" item)
   - Route simple questions to the current pipeline and complex ones to an iterative plan → search → read →
     refine loop, writing into the Claim Ledger as a claim-evidence graph
   - Hard caps on iterations and LLM calls. Agentic queries cost several times more than single-pass RAG
   - Reference designs: ADORE (arXiv 2601.18267), the "RAG → Deep Research" KDD 2026 tutorial

7. **S7. Dual-model extraction with disagreement flags** - 8h (addresses Critical Gaps #5 and #6)
   - Extract each table with two different models and flag rows where they disagree for human review
   - A living-review study found that 342 two-model answers in its test set, 87% of the total, were concordant, with 0.94 accuracy among them.
     Disagreement is a cheap confidence signal

8. **S8. Qdrant native BM25** - 4h, low priority
   - Qdrant 1.20 ranks BM25 directly on a full-text index. That could replace the client-side sparse
     vectors. Check the Qdrant Cloud cluster version first

9. **S9. Visual page retrieval (ColQwen-style)** - later, part of the Medium-Term "Multimodal Support" item
   - Embeds page images, so tables and figures are searchable without parsing. Storage is about 150–500 KB per
     page against 5–20 KB for text. Test on a figure-heavy subset only

**Sources consulted (6 Nov 2026):**
[OmniDocBench](https://github.com/OpenDataLab/OmniDocBench) ·
[MinerU releases](https://github.com/opendatalab/MinerU/releases/tag/mineru-3.3.1-released) ·
[MinerU on PyPI](https://pypi.org/project/mineru/) ·
[Embedding models for RAG 2026](https://blog.premai.io/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting) ·
[Cohere Rerank 4 Fast (Pinecone)](https://docs.pinecone.io/models/cohere-rerank-4-fast) ·
[Cohere deprecations](https://docs.cohere.com/v2/docs/deprecations) ·
[Reranker comparison (Agentset)](https://hn.jakechampion.name/reader/https://agentset.ai/blog/best-reranker) ·
[Qdrant 1.20](https://qdrant.tech/blog/qdrant-1.20.x/) ·
[Qdrant 1.19](https://qdrant.tech/blog/qdrant-1.19.x/) ·
[RAG evaluation 2026](https://blog.premai.io/rag-evaluation-metrics-frameworks-testing-2026) ·
[FRANQ, ACL 2026 Findings](https://preview.aclanthology.org/ingest-acl/2026.findings-acl.338/) ·
[ADORE](https://arxiv.org/html/2601.18267v1) ·
[RAG → Deep Research tutorial](https://tutorial.lunadong.com/) ·
[LLM numeric extraction in dentistry](https://docta.ucm.es/entities/publication/aab87bf3-d044-4322-90e6-ac074d470128/full) ·
[OpenExtract](https://arxiv.org/abs/2603.13338) ·
[otto-SR, ISPOR 2026](https://www.ispor.org/heor-resources/presentations-database/presentation-cti/ispor-2026/poster-session-2-4/automation-of-systematic-reviews-with-large-language-models) ·
[Visual document retrieval](https://mixpeek.com/guides/visual-document-retrieval) ·
[Gemini 4 status, Aug 2026](https://andrew.ooo/answers/is-gemini-4-out-yet-august-2026-status/)

---

### 🏷️ Rename to 3ie Evidence Assistant

1. **R0. Rename product, repo, code and infrastructure** - 12h
   - Step-by-step plan with checks and undo for each step: [docs/RENAME_PLAN.md](RENAME_PLAN.md)
   - Do step 1 (code on a branch) together with S1, since both touch `settings.py` and `rags.py`

---

### Immediate (Next Sprint)

1. **Full Extraction Dataset + Human Validation** - 6h (reduced from 8h)
   - ✅ **V3-V6 COMPLETE:** 54 studies, 4 table orientations, multi-language, prose + figure fallbacks
   - ✅ **Step 1 COMPLETE:** Full corpus extraction → 92 studies (86 with data, 6 empty), 12,366 rows
   - **Step 2:** Human review of extracted data (spot-check ~10% of rows) ⬅️ **IN PROGRESS**
   - **Step 3:** Document FP/FN, calculate precision/recall
   - **Output:** `extraction_pipeline/outputs/full_corpus_for_validation.csv` (current: 12,366 rows)
   - Files: `extraction_pipeline/cli_v2.py`, `extraction_pipeline/combine_outputs.py`

2. **Domain-Specific Intervention Components** - 6h
   - Build LLM-based component extractor per `DOMAIN_CONFIGS` in `schemas.py`
   - Add CLI arg `--domain graduation|education|health`
   - Test on 3 domains
   - Files: `extraction_pipeline/pipeline.py`, `src/extraction/schemas.py`

3. **Study Design Filter in Evidence Panel** - 4h
   - Add dropdown to filter evidence by study design (RCT, DiD, etc.)
   - Files: `frontend/src/components/EvidencePanel.tsx`

4. **"I Don't Know" Explicit Refusal** - 2h
   - When retrieval confidence is below threshold, explicitly refuse to answer
   - Prevents hallucination when no good sources found
   - Files: `src/agents/evidence_assistant_agent.py`, `src/generation/claim_ledger.py`

### Short-Term

1. **~~Extraction Pipeline → Production Integration~~** - 12h ✅ **COMPLETE**
   - ✅ Supabase `extracted_estimates` table with 28 columns
   - ✅ API endpoints: `/extraction/studies/{id}/effects`, `/extraction/chatbot-context`, etc.
   - ✅ Supabase loader: `python -m extraction_pipeline.adapters.supabase_loader --all`
   - ✅ Chatbot integration models: `QuantitativeContext`, `ChatbotEffectContext`
   - Files: `api/routes/extraction.py`, `extraction_pipeline/adapters/supabase_loader.py`
   - **Next:** Run migration, upload data, build Evidence Panel component

2. **Embedding Model Comparison: Cohere vs Voyage 4** - 6h ➡️ **Superseded by SOTA Upgrade S3**
   - Benchmark Voyage AI 4 (launched Jan 15, 2026) against current Cohere embed-v4
   - Metrics: retrieval accuracy, speed, cost per 1M tokens
   - Files: `evaluation/benchmark_embeddings.py`

3. **~~PDF Parser Comparison: MinerU vs MonkeyOCR~~** - ⚠️ **Superseded by TVET Transfer T4**
   - ✅ Both parsers integrated (MinerU on a T4 GPU, MonkeyOCR as a VLM on an A10G). The integration has been uncommitted since 23 Feb 2026
   - ✅ Proxy comparison run on 5 papers: `evaluation/compare_parsers.py` → `evaluation/parser_comparison_results.json` (table counts and numeric density, with no human key)
   - ⚠️ The TVET bake-off scored MonkeyOCR lowest against a human key (table recall 0.075, decimal recall 0.543, timeouts above 24 pages). Do not make it the default
   - **Decision needed:** commit the MonkeyOCR integration as an experimental path, or drop it

2. **Improve Faithfulness** - 8h
   - Current: 66.47%, Target: 70%+
   - Prompt tuning in Langfuse experiments
   - A/B test synthesis prompts

3. **Contextual Summarization (RCS)** - 8h
   - Before synthesis, LLM summarizes each chunk's relevance to query
   - Filters low-relevance chunks before passing to Claim Ledger
   - Files: `src/rag/retrieval.py`, `src/generation/claim_ledger.py`

4. **Smart Citations** - 12h
   - Classify citations as supporting/contrasting using OpenAlex data
   - Display: "38 Supporting | 3 Contrasting" badges
   - Files: New `src/enrichment/citation_classifier.py`

5. **Consensus Meter** - 16h
   - Visual: "Strong Support: 85%, 17/20 studies"
   - Extend ClaimLedger to track support/contradict per citation
   - Files: `src/generation/claim_ledger.py`, frontend component

6. **Self-Consistency** - 8h
   - Generate 3 answers with temperature > 0, select most consistent
   - Improves accuracy on complex synthesis questions
   - Files: `src/generation/claim_ledger.py`

### Medium-Term

1. **Agentic RAG** - 20h ➡️ **Now SOTA Upgrade S6 (deep-research mode)**
   - Multi-step: Search → Review → Refine → Gather → Answer
   - Agent decides when to iterate on search

2. **Multimodal Support** - 24h
   - Extract tables/figures during PDF parsing
   - Vision LLM for captions, store in Qdrant

3. **Document Enrichment Pipeline** - 40h
   - Geography, intervention type, effect sizes extraction
   - Enables quantitative queries across studies

### Long-Term

1. **Systematic Review Workflow** - 40h
   - Protocol → Screening → Extraction → PRISMA flow

2. **Research Report Generation** - 30h
   - Auto-generate structured reports from evidence

3. **Embeddable Widget** - 16h
   - Embed 3ie Evidence Assistant on external sites (e.g., 3ie portal)

4. **Security Hardening** - 8h
   - Rate limiting, input validation, audit logs

5. **TruLens Evaluation** - 4h
   - Alternative RAG evaluation framework
   - Reference: https://www.trulens.org/

6. **Slack/Teams MCP Integration** - 20h
   - Let researchers query 3ie Evidence Assistant from Slack without switching apps
   - Example: `@evidence-assistant What effect sizes for cash transfers?`
   - Reference: [MCPs for Developers](https://www.oreilly.com/radar/mcps-for-developers-who-think-they-dont-need-mcps/)

7. **Context7-style Live Docs MCP** - 12h
   - Pull up-to-date methodology docs into agent context
   - Sources: 3ie methods guidance, PRISMA guidelines, Cochrane handbook
   - Reference: [Context7 MCP](https://block.github.io/goose/docs/mcp/context7-mcp)

8. **Aardvark** - 12h
   - Test security
---

## Success Metrics (Targets)

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **Extraction: Study coverage** | 86/92 (93%) | 95%+ | 🟡 Close |
| **Extraction: Rows extracted** | 12,366 | - | ✅ |
| **Extraction: Table orientations** | 5 types | - | ✅ |
| **Extraction: Languages** | EN, ES, FR, PT | - | ✅ |
| **Extraction: Fallbacks** | Prose + Figures | - | ✅ |
| **Extraction: Precision** | ❓ Unknown | 90%+ | ❌ Needs ground truth |
| **Extraction: Recall** | ❓ Unknown | 80%+ | ❌ Needs ground truth |
| **Extraction: Coefficient accuracy** | ❓ Unknown | ±0.01 | ❌ Needs ground truth |
| **Extraction: SE accuracy** | ❓ Unknown | ±0.005 | ❌ Needs ground truth |
| **Extraction: Classification accuracy** | ~88% (self-measured) | 95%+ | 🟡 Needs validation |
| **Extraction: Confidence scores** | None | Per-row scores | ❌ Not started |
| **Extraction: Regression tests** | None | 30+ test cases | ❌ Not started |
| **RAG: Faithfulness** | 66.47% | 70%+ | 🟡 In progress |
| **RAG: Citation Recall** | 98.86% | 70%+ | ✅ |

---

## Completed This Session (Feb 23, 2026)

| Feature | Description |
|---------|-------------|
| **MonkeyOCR Integration** | Added `run_monkeyocr()`, `process_pdf_monkeyocr()`, `monkeyocr_image` to Modal pipeline. Outputs to `outputs/monkeyocr/` in R2. CLI: `--action monkeyocr`. |

## Completed This Session (Jan 31, 2026)

| Feature | Description |
|---------|-------------|
| **Modular Refactor** | Split pipeline.py into `core/`, `adapters/`, `postprocessing/` modules |
| **Error Handling** | `ErrorAccumulator` with stage context, `LLMFailureType` enum |
| **LLM Client** | Centralized `LLMClient` with caching, `sanitize_llm_response()` |
| **Schema Adapter** | `ColumnNames` constants, `normalize_authors()`, consistent field mapping |
| **Effect Size Assumptions** | Explicit `effect_size_assumption` column tracks calculation assumptions |
| **CLI v2** | New `cli_v2.py` with `--fast`, `--minimal`, `--no-prose`, `--no-figures` flags |

## Completed (Jan 29, 2026)

| Feature | Description |
|---------|-------------|
| **V4: SE-split parser** | Handles tables where SE is in separate rows below coefficients |
| **V4: European format** | Converts comma decimals (0,15) to dots (0.15) |
| **V4: Treatments-in-cols** | Extracts tables with treatment groups as column headers |
| **V5: Multi-language** | Spanish, French, Portuguese keywords for treatment detection |
| **V6: Figure extraction** | LLM extracts effects from figure captions when tables unavailable |
| **V6: Prose extraction** | LLM extracts effects from narrative text as fallback |
| **Regression check** | Verified V4 changes don't break previously working papers |

---

## References

- [PaperQA2](https://github.com/future-house/paper-qa) - Agentic RAG benchmark
- [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) - 49% improvement technique
- [RAG-Fusion](https://arxiv.org/abs/2402.03367) - Multi-query retrieval
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) - LLM context position bias
- [Binary Quantization](https://qdrant.tech/documentation/guides/quantization/) - Qdrant guide
- [Elicit](https://elicit.com/) - Systematic review automation
- [Scite](https://scite.ai/) - Smart Citations
- [TruLens](https://www.trulens.org/) - RAG evaluation framework


