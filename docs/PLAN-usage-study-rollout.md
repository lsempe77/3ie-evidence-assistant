# Plan: land the PDF reader, then act on the usage study

Scope: everything outstanding from the 11-12 November 2026 sessions. Two workstreams: the in-app PDF reader (built, fixes applied, not committed or pushed), and the chunk-use study's conclusions (analysis only, nothing wired in).

How the app deploys, for reference:
- Frontend: Vercel, from `frontend/` (`frontend/vercel.json`), on push to `main`.
- API: Railway, Docker image from `Dockerfile` (copies `api/` and `src/`), healthcheck `/health`, on push to `main`.
- Answer-quality gate: `.github/workflows/benchmark.yml` runs `python evaluation/gate.py` on pull requests that touch `src/**`, `api/**`, `evaluation/**` or `requirements*.txt` (quick 5 questions about $0.20, full 20 about $1), compared against `evaluation/benchmark/baseline.json`.
- Tests: `pytest` (`testpaths = ["tests"]`), `ruff` and `mypy` configured in `pyproject.toml`.

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

Steps:
- [ ] Wire `src/extraction/relevance_labels.py` into ingestion, before embedding. Decide the layer: filter the parsed units before chunking (`units_from_content`) so a chunk never mixes kept and dropped text. The production indexer is `src/ingestion/indexer.py` (`ChunkIndexer`); today it applies no role filter.
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
