# Model and pipeline review, November 2026

**Question.** The app still answers with models and a pipeline from 2024. Which answer pipeline and which
models should it use now?

**Short answer.** Change the pipeline first. Reading every relevant study and then synthesising raised the
share of the review's conclusions that answers support from 0.29 to about 0.49, with every model tried. The
choice of answer model moved the score by less than 0.03, which is within the noise of a single run. Use
Claude Haiku 5.5 for both reading and answering by default, and offer a stronger model as an optional
"deep" mode.

## How this was measured

- **Benchmark:** 20 questions on the "Poverty graduation programmes" collection (97 documents). Gold
  answers come from 3ie's systematic review brief on graduation programmes (December 2025): 49 claims a
  correct answer should make, statements that count as errors, and three evidence-gap questions. See
  `evaluation/benchmark/graduation_sr_v0.yaml`.
- **Included studies:** the review's master list of 114 quantitative studies, matched to the collection.
  86 are held. See `evaluation/benchmark/graduation_included_studies.csv`.
- **Scoring:** two judges from different model families (Claude Sonnet 5.5 and GPT-6 Sol) mark each gold
  claim supported (1), partly supported (0.5), contradicted or missing (0). Their means differed by 0.02
  to 0.08 on six configurations and by 0.13 on GPT-4o, so the table reports their average. Seven claims
  need the review's pooled effect sizes or cost model rather than any one study's text. They are tagged
  `pooled`, and a second score covers the other claims only.
- **Runner:** `evaluation/run_benchmark.py`. Results: `evaluation/results/benchmark_graduation_sr_v0_*_2026-11-09.*`.

## Results

| Pipeline and answer model | All claims | Study-level claims | Gap questions answered as gaps | Contradicted / error statements | Seconds per answer |
| --- | --- | --- | --- | --- | --- |
| Current app: claim ledger, gpt-4o-mini and gpt-4o | 0.29 | 0.31 | 0 of 2 | 1 / 2 | 32 |
| Read then synthesise: GPT-6 Sol | 0.50 | 0.55 | 1 of 1 judged | 0 / 0 | 25 |
| Read then synthesise: Claude Sonnet 5.5 | 0.49 | 0.56 | 2 of 2 | 1 / 0 | 25 |
| Read then synthesise: Claude Haiku 5.5 | 0.49 | 0.54 | 2 of 2 | 0 / 0 | 26 |
| Read then synthesise: GPT-4o (2024) | 0.49 | 0.54 | 2 of 2 | 0 / 0 | 22 |
| Read then synthesise: Gemini 3.8 Flash | 0.48 | 0.55 | 1 of 2 | 2 / 1 | 38 |
| Read then synthesise: DeepSeek V4.1 Flash | 0.47 | 0.52 | 2 of 2 | 0 / 1 | 35 |

All "read then synthesise" rows share one reading pass by Claude Haiku 5.5 over 10 to 37 studies per
question.

## What changed the answers

The current app writes from about ten studies' passages through a chain of about 13 sequential model
calls. It lists facts study by study, calls effects "significant" or "sustainable" where the review says
"modest", and never says that evidence is thin.

The new pipeline makes three moves:

1. **Retrieve** a 300-passage pool for the question as asked, with no rewriting by a model, and rerank it.
2. **Read** every study with a passage above a low floor. A small model, run in parallel, says whether the
   study answers the question and what it found, with a quote and a page.
3. **Synthesise** from all relevant findings. The prompt asks for counts by direction ("18 of 25 studies")
   and for sizes as reported, honestly qualified. It keeps short and long term apart, says plainly when the
   collection cannot answer, uses the question's language and cites every sentence.

Example, on income and consumption. The new answer reports that 18 of 25 relevant studies point in a
positive direction. It calls consumption gains "modest to moderate" (0.17 to 0.36 SD in Bangladesh, 11% in
Ghana) and income effects less certain. It lists the null results in Colombia, Paraguay and Yemen.

## Cost per question (estimates)

| Step | Estimate |
| --- | --- |
| Retrieval and reranking of 300 passages (Cohere) | about $0.006 |
| Reading 10 to 37 studies with Claude Haiku 5.5 | about $0.02 (measured: $0.46 for 20 questions) |
| Answer with Claude Haiku 5.5 | about $0.001 |
| Answer with Claude Sonnet 5.5 or GPT-6 Sol | about $0.008 |

The answer costs are derived by subtracting judge costs from each run's measured spend, so treat them as
approximate. A question costs about three US cents with Haiku throughout. Judging is an evaluation cost
only.

## Recommendations

1. **Adopt "read then synthesise" as the default answer path.** Retire query rewriting (HyDE,
   decomposition, step-back, variants), model-guessed filters, the claim ledger and the LlamaIndex wrapper,
   whose first import alone takes 27 seconds.
2. **Models:** Claude Haiku 5.5 for reading and for answers by default. Offer Claude Sonnet 5.5 or GPT-6
   Sol as an optional "deep" mode. Before fixing the default, repeat the three leading configurations two
   more times, because the differences between models are within single-run noise.
3. **Next limit, coverage.** Even a 300-passage pool reaches only 10 to 37 of the 86 held studies on broad
   questions. Retrieve at study level first (rank whole studies, then fetch passages within each).
4. **Next limit, pooled conclusions.** Claims such as "programmes targeting women yield smaller income
   gains" come from comparing effect sizes across studies. That needs the quantitative layer in
   `docs/RAG_PIPELINE_PLAN.md`: extract effect sizes per study, then compare them.
5. **Product:** show "read 31 studies, 25 relevant" with the answer, and list the per-study findings in the
   Sources panel. They are the evidence table users need to check the synthesis.

## Limits of this review

- One run per configuration. Single questions swung by up to 0.25 between runs of the same pipeline.
- One collection and one review. The benchmark should grow to other topics before the switch-over.
- The judges are models. A sample of answers should be checked by 3ie reviewers.
- Seven of the 49 gold claims need pooled analysis, which no configuration here can produce.
