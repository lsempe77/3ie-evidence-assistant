# Plan: land the PDF reader, then act on the usage study

Scope: everything outstanding from the 11-12 November 2026 sessions. Two workstreams: the in-app PDF reader (built, fixes applied, not committed or pushed), and the chunk-use study's conclusions (analysis only, nothing wired in).

How the app deploys, for reference:
- Frontend: Vercel, from `frontend/` (`frontend/vercel.json`), on push to `main`.
- API: Railway, Docker image from `Dockerfile` (copies `api/` and `src/`), healthcheck `/health`, on push to `main`.
- Answer-quality gate: `.github/workflows/benchmark.yml` runs `python evaluation/gate.py` on pull requests that touch `src/**`, `api/**`, `evaluation/**` or `requirements*.txt` (quick 5 questions about $0.20, full 20 about $1), compared against `evaluation/benchmark/baseline.json`.
- Tests: `pytest` (`testpaths = ["tests"]`), `ruff` and `mypy` configured in `pyproject.toml`.

---

## Status log

- 12 Nov 2026: Phase 0 done. Review fixes committed as `c7deee1` (viewer) and `3aaea00` (study), the plan as `04fd1f7`; `main` pushed. Vercel and Railway deployed and healthy (`/health` 200, all components true). The reader was confirmed working live.
- 12 Nov 2026: slow PDF opening fixed in `1c5c685` by windowing page rendering. This also does Phase 5.
- 12 Nov 2026: Phase 1 implemented in `67fbfd6` (reader relevance by question kind) and confirmed on the full 211-question set. Relevant studies per question rose from 15.2 to 18.3 overall and in every category (implementation 0.7 to 1.6, context 4.2 to 9.3, side effects 3.8 to 6.0, mechanisms 14.4 to 19.2, effects 27.0 to 29.7). Supporting quotes rose 3,194 to 3,863; quotes not verbatim fell 188 (5.9%) to 178 (4.6%); the noise share of quotes rose 7.1% to 8.6%. Full benchmark gate passed (0.567 vs 0.552). The re-run is in `report.md`; the previous run is `runs.baseline.jsonl`.
- 12 Nov 2026: run infrastructure fixed. Non-ASCII characters in console output crashed the Windows cp1252 handler: the reranker log arrow (`b6ccdf0`) flooded output, and the study's failure marker (`762d80c`) aborted a run at 18 of 211. The study now logs ASCII and gathers with `return_exceptions=True` so one failed question cannot stop a batch.
- 12 Nov 2026: the Sphinx docs job now passes; GitHub Pages was not enabled, so it was enabled (custom domain `sempe.dev` was already configured).
- Unrelated, resolved: the "Deploy Sphinx Docs to GitHub Pages" job failed on every push because GitHub Pages was not enabled (404 from `actions/deploy-pages`). Pages is now enabled and the job passes.

---

## Phase 0. Land the reader, do not let the fixes rot

Status: the reader is committed on local `main` (`15b63b4`, `f8f4fb0`, `d47c85e`), the study is `ec24057`, and seven review fixes are uncommitted in the working tree.

Steps:
- [ ] Commit the seven review fixes (viewer: highlight-overlap crash, effect split, page-field sync; `page.tsx` and `rags.py` `highlight` flag; `usage_study.py` normalizer + cache; `relevance_labels.py` prompt boundary). Suggest two commits: one for the viewer, one for the study script and prompt.
- [ ] Local checks: `pytest`, `ruff check .`, `mypy` (per `pyproject.toml`); frontend `npm run lint`, `npx tsc --noEmit`, `npm run build` in `frontend/`.
- [ ] Smoke test the viewer in a browser: open a citation, confirm the passage highlights, search a word that appears inside the cited passage (this was the crash), step matches, scroll and confirm the page field tracks, open the new-tab link.
- [ ] Push `main`. This deploys the API (Railway) and the frontend (Vercel).
- [ ] Verify live at the Vercel URL on the graduation project: the reader appears inside the chat view instead of the browser's iframe viewer.
- [ ] Check a private collection while signed in (the fetch uses the Authorization header; a blob URL is required).

Rollback: revert the commit and push, Vercel and Railway redeploy the previous build.

Open item carried from review: page virtualization (`#5`) was deferred. The client finds the cited passage by searching every page's text, so windowing cannot be done safely without a different source for the cite page. Decide later (see Phase 5).

---

## Phase 1. Make questions that are not about effects work

This is the study's highest-value fix and needs no re-index. It is a prompt change in `src/agents/study_synthesis.py`.

Problem (with lines): `READER_PROMPT` requires "direction and size" (`:66`) and says a passage that mentions the topic without results is not relevant (`:74`); `ANSWER_PROMPT` counts studies by direction (`:95-101`). Result: 27 relevant studies per effects question, 0.7 per implementation question.

Steps:
- [ ] Classify the question kind (effects, subgroups, durability, costs, implementation, mechanisms, design, context, variants, side effects, gaps). Either a small-model call or a keyword classifier; or write one type-aware prompt that never closes the door on non-effect evidence (more robust, slightly less sharp).
- [ ] Rewrite `READER_PROMPT`: add the question kind and a per-kind definition of what counts as evidence; state that an implementation, context, design, cost or mechanism passage is relevant even with no effect size; add a `kind` field to the reader JSON; drop the effect-only relevance rule for non-effect questions. Keep the own-evidence and secondhand rules.
- [ ] Adapt `ANSWER_PROMPT`: for non-effect questions, answer in their own terms (how, to whom, how much, at what cost) and do not force counts by direction. Keep the citation rule.
- [ ] If breadth alone is not enough, check the actual passages sent for a few implementation questions. Retrieval sends at most 4 passages per study (`PASSAGES_PER_STUDY`, `:47`); if the delivery or design text is crowded out, raise the cap or retrieve by the question's own terms.

Test:
- [ ] `pytest` and the quick gate locally on a small subset.
- [ ] Full re-run on the same 211 questions: `python evaluation/usage_study.py run --project-id <uuid>` then `analyse`. Cost about $11.
- [ ] Target: implementation relevant-studies-per-question rises from 0.7; effects and other categories do not fall.
- [ ] Run the benchmark gate (`python evaluation/gate.py --mode quick` then `--mode full`) to confirm no regression against `evaluation/benchmark/baseline.json`.

Rollback: one file; revert the prompt change.

---

## Phase 2. Filtered index (drop the noise paragraphs)

Follows the study finding that other studies' findings (11%), background (9%) and boilerplate (11%) are 31% of what the reader sees but 7% of the quotes.

Status (12 Nov 2026): the reusable core is in place and tested (`relevance_labels.filter_units`, `tests/test_relevance_filter.py`, 5 tests pass), with no change to production behaviour. The wiring and the re-index are pending the design decision below.

Hook points found: the parser writes the content list to R2 at `rags/{project}/outputs/json/{doc_key}.json` (`src/ingestion/pdf_processor.py`), which is what `units_from_content` reads and what the study labelled. Chunks are written only by `ChunkIndexer.index_nodes`, and its only caller is the admin `/ingest` route (`api/routes/admin/collection.py:271`), which loads markdown from a directory and chunks that. Indexing is therefore a separate operator step, not part of upload.

Decision needed: filter at the parsed-unit level (matches the study exactly, but the ingest route must be given the content list and build documents from kept units) or at the chunk level after markdown chunking (least invasive, but a chunk's role approximates a paragraph's). Either way the re-index must be run deliberately, and the labels should be cached per document so the re-index is deterministic and the model is not re-called.

Steps:
- [x] Add the reusable filter (`relevance_labels.filter_units`) with tests. Done.
- [ ] Decide the filter layer (parsed units or chunks); see above.
- [ ] Wire the chosen layer into ingestion before embedding, with the label cache, fail-open on model failure, and a setting to enable it.
- [ ] Keep: abstract (always), own findings, method, intervention, setting, cost, limitation. Drop: references, boilerplate, background, other studies' findings.
- [ ] Never rewrite text: labels are per paragraph and text stays verbatim, so quotes still map to a page for citation and highlighting.
- [ ] Store the per-document labels so re-indexing is deterministic and does not re-call the model.
- [ ] Fail open: keep text when the model call fails (the prototype returns `unlabelled`).
- [ ] Re-index the collection (embed only the kept chunks). Labelling is about $0.50 for 97 papers; re-embedding is the main cost.

Test:
- [ ] Spot-check retrieval for effects and non-effect questions: methods, intervention and setting must still be retrieved.
- [ ] Re-run the noise share (other_study + background + boilerplate) and confirm it falls well below 31% while quotes from kept roles hold.
- [ ] Benchmark gate quick and full.

Rollback: keep the previous index snapshot; re-index from the pre-filter config if quality drops.

---

## Phase 3. Quote fidelity

The study found 188 of 3,194 supporting quotes (6%) are not verbatim in any paragraph; a looser match gives 117 (3.7%). This matters for citations and PDF highlighting.

Steps:
- [ ] Inspect a sample of the 188 quotes: are they paraphrases by the reader, or text the paragraph index missed?
- [ ] If the reader paraphrases, tighten the reader's quote instruction and validate that the quote is a substring of the passages before accepting it.
- [ ] Re-measure the non-verbatim rate on the 211-question set.

---

## Phase 4. Secondhand guard (optional, partly subsumed by Phase 2)

103 quotes still came from other-study paragraphs because `cites_other_study` only matches author-year citations.

Steps:
- [ ] If Phase 2 ships, other-study paragraphs are out of the index, so this guard matters less. Otherwise, strengthen `src/extraction/secondhand.py` or add a check that a quote exists in a kept paragraph.

---

## Phase 5. Page virtualization (deferred, product decision)

- [ ] Decide whether to window page rendering. Safe only with a different source for the cite page (for example the API returning the matched page) or a progressive render-and-search loop. Requires browser testing.

---

## Cross-cutting

- Costs: Phase 1 full re-run about $11; Phase 2 labelling about $0.50 plus a re-index; the CI gate about $0.20 (quick) and $1 (full) per run.
- Caveats to carry: paragraph roles come from one model (`claude-haiku-5.5`) with no human agreement check; the 6% non-verbatim figure is definition-dependent (4% to 6%).
- Ordering: Phase 0 first (deploy what is tested). Phase 1 is cheap and independent, so it can go before Phase 2. Phase 2 changes the index, so it needs a re-index and the most testing. Phase 3 can run after Phase 1.
