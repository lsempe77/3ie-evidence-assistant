# Normalisation of table results

Status: design note, 13 November 2026. This scopes the work behind N6 in [ROADMAP.md](ROADMAP.md) and the meta-analysis step in [RAG_PIPELINE_PLAN.md](RAG_PIPELINE_PLAN.md). It is a plan, not an implementation.

## The gap, measured

`src/extraction/table_estimates.py` reads one table with a model, then parses the cells in tested code. It records the literal cell text, which is the right foundation. What it does not do is produce a normalised, meta-analysis-ready record. Across the 10,014 rows in `extraction_pipeline/outputs/*/extracted_data.csv` (97 studies), the field coverage is:

| Field | Rows with a value | Share |
|---|---|---|
| `coefficient` | 10,014 | 100% |
| `literal_cell_text` | 10,014 | 100% |
| `standard_error` | 5,908 | 59% |
| `p_value_text` | 3,204 | 32% |
| `significance` | 2,804 | 28% |
| `sample_size` | 701 | 7% |
| `ci_lower` | 0 | 0% |
| `t_statistic` | 0 | 0% |
| `effect_size_assumption` | 0 | 0% |

So the estimate and its provenance are reliable, and everything needed to standardise it is mostly missing. The significance values are only stars (`***` 1,793, `**` 504, `*` 451) or the words "significant" (9) and "not significant" (3). The p-value text is either derived from stars (`p<0.001` 1,793, `p<0.01` 509, `p<0.05` 455) or a raw value, sometimes messy (`[0.000]`, `1.0`, `0.0`, `NS`).

## Data available

- **Our corpus.** `extraction_pipeline/outputs/full_corpus_for_validation.csv` (28 columns) and the per-study `extracted_data.csv` files (10,014 rows in total), which have the richer 43-column schema including `literal_cell_text`, `p_value_text`, `t_statistic`, `n_clusters`, `cohens_d`, `effect_variance`. Also `results_tables_*.csv`, which classifies tables and records `has_stars`, `has_se`, `has_pvalue`, `rows`, `cols`, `section`, `is_continuation`. That is most of a layout taxonomy already.
- **The human key.** `data/8WR QEX Combined.xlsx` (443 rows, 125 columns) is a full meta-analysis sheet: `Coeff reg`, `SE reg`, `Tstat reg`, `CI_LB reg`, `CI_UP reg`, `P value exact`, cluster and N counts, `# periods`, and the standardised outcomes `d`, `yi`, `var(d)`, `vi`, `se(g)` with a `Formula Used` code (5 in 142 rows, 6 in 300). This is the target schema, and it is the ground truth for normalisation.
- **`data/8 week SR OM Combined.xlsx`** (19 columns) is an outcome-mapping sheet: which outcome to extract and where (page, table, row, column). Use it to pick outcomes, not to normalise numbers.
- **8w-sr OM_QEX v2.** `pipelines/8w-sr/OM_QEX/om_qex_extraction_v2/` (outside this repo) writes `effect_size`, `ci_lower`, `ci_upper`, `p_value`, `standard_error`, `sample_size` and maps stars to p-values, with a validation phase (`phase7_qex_validation.py`) and a vision fallback (`phase5_pdf_vision.py`). Use it for conventions and as a baseline to beat.
- **TVET.** `pipelines/TVET/ground_truth_datasets/` has human table keys (`is_true_table`, `true_caption`, `true_page`, `row_labels`, `column_labels`) and outcome hand-checks whose `literal_text` is the raw printed form, for example `0.570 (0.179) {0.001;...}`. `CHECKER_INSTRUCTIONS.md` fixes the conventions: printed folio not viewer page, verbatim row and column labels, and awkward tables count. Use it to test table detection and to read the raw forms, not the numbers.

## Target record

One row per estimate, aligned to the 8WR key, with provenance kept:

| Group | Fields |
|---|---|
| Estimate | `estimate`, `se`, `t_statistic`, `p_value`, `p_text`, `stars`, `ci_low`, `ci_high`, `ci_level` |
| Design | `n_treatment`, `n_control`, `n_total`, `n_clusters`, `n_periods`, `control_mean`, `control_sd` |
| Standardised | `effect_size_assumption`, `d`, `var_d`, `yi`, `vi`, `se_g`, `formula_used` |
| Identity | `outcome_name`, `outcome_category`, `treatment_arm`, `subgroup`, `is_main_effect`, `is_subgroup`, `is_spillover`, `is_cost`, `is_mechanism`, `reverse_sign` |
| Provenance | `literal_cell_text`, `table_number`, `table_caption`, `page`, `row_label`, `column_label`, `study_id` |

## Taxonomy of presentation variants

Each variant needs a detector, a parser, and a test. Real forms from the corpus:

1. **Coefficient and SE in one cell.** `0.15*** (0.05)`, `356.9** (152.5)`, and the concatenated `3.55***1.132` where the SE lost its separator. Parse the number before the stars as the estimate and the parenthesised or trailing number as the SE, then treat the pair as suspect when no separator exists and record it.
2. **Stars.** `***`, `**`, `*`, `†`, `ns`, `NS`, "significant", "not significant". Map to p-bounds, never to a point p (`***` to p<0.001, `**` to p<0.01, `*` to p<0.05, `†` to p<0.10), and keep `stars` as given.
3. **Exact p.** `0.010`, `[0.000]`, `<0.001`, `p=0.478`. Strip brackets, treat `[0.000]` as below the print precision, and never read `1.0` or `0.0` as real p-values without a check.
4. **Confidence intervals.** Brackets `[0.07, 0.23]`, parentheses, `±`, two columns (`CI_LB`, `CI_UP`), and a separate row. Record `ci_level` when stated (95% default).
5. **Test statistics.** `t`, `z`, `F`, `chi2`, given directly or by "SE =". Derive p from the statistic and df only when df is known.
6. **Sample sizes.** Per arm, total, clusters (the 8WR key separates cluster counts from N), and periods. Do not treat a cluster count as an individual N.
7. **Scale and units.** Levels versus logs, percent versus percentage points, per-capita versus total, index versus currency, and nominal versus PPP (the 8WR key keeps these apart). Record `effect_size_assumption` so the standardisation is explicit.
8. **Sign and direction.** `reverse_sign` for outcomes where a fall is good, and the sign convention of the printed coefficient.
9. **Table layouts.** Treatments in columns, SE in the row below the coefficient, transposed, multi-panel (Panel A/B), multi-arm, subgroup rows, rotated and borderless tables. `results_tables_*.csv` already flags `has_stars`/`has_se`/`has_pvalue`, rows and columns.

## Table interpretation

Reading the structure is separate from reading the values. `src/extraction/table_structure.py` does the structure deterministically, with tests in `tests/test_table_structure.py` (10 pass):

- **Multi-page stitching.** `stitch_units` merges a table continued on the next page when the header repeats or the caption says "continued", and the pages are adjacent. The pipeline sends one Markdown item per parsed table, so this runs before extraction.
- **Grid and notes.** `parse_markdown_table` splits header, body and note lines using the Markdown separator. `parse_conventions` reads the notes for "standard errors in parentheses", "t-statistics in brackets", "95% CI" and the star map (`*** p<0.01, ** p<0.05, * p<0.1`).
- **Column roles.** `infer_columns` assigns estimate, SE, t, z, p, CI bounds, N, mean and SD from the header, the notes and a value profile, after expanding abbreviations (ATT, ATE, ITT, s.e., obs, sd, pp), so "ATT" and "confidence interval upper" both resolve.
- **Arithmetic resolution.** `resolve_consistency` labels an unlabelled numeric column when the estimate divided by it is a whole t-like ratio, which separates an SE column from a differently scaled one.
- **Confidence and warnings.** `interpret_table` returns the roles, the combined-cell flag (`0.52*** (0.12)`), the star map, a confidence and warnings, so a low-confidence table is flagged for review instead of trusted.

Deliberate limit: a small decimal column is not guessed to be a p-value from its values alone, because an SE, a coefficient and an elasticity look alike. A column stays unknown until a header, a note or the arithmetic decides it. The module interprets structure only and does not call a model.

### Coverage on the corpus

Run over the 1,617 parsed tables in the collection (`evaluation/table_structure_audit.py`, report in `evaluation/results/table_structure_audit_2026-11-14.md`), the interpreter reads 460 as results tables (28%). Of those, it finds a standard error, in a column or inside the estimate cell, for 275 (60%), and a p-value for 75 (16%); a confidence interval for only 4 (1%). It leaves 39% of the result-table columns unknown. Layouts split 1,545 statistics in columns to 72 statistics in rows.

Three layout classes were found in the data, and the third was added after the first run. Most tables put one statistic per column. A second class puts outcomes or models in the columns and `Coefficient`, `Standard error` and `Observations` in the first column as rows, which is now detected as the statistics-in-rows layout. A third class has outcomes in the columns with each cell holding `estimate*** (SE)` and no role labels at all, which raised the results-table count from 410 to 460 once detected. Spanish, Portuguese and French headers are folded and matched.

The p-value figure is low because p is usually stated once in the notes as a star map rather than in its own column; the star map is parsed (305 tables, 19%), so the value is available even when there is no p column. Closing the remaining 39% of unknown columns needs a row-label glossary (outcome labels such as `(1) Assets`) rather than more header terms.

Next: use these roles inside `table_estimates.py` before the model call, and treat a low-confidence table as a review flag rather than trusting it.

### Using TVET's table typing and row rules

TVET already solved two adjacent problems (`pipelines/TVET/pipeline/`, outside this repo): telling a results table from a descriptive one (`prompts/phase2_table_filtering.txt`), and excluding rows and columns that are not outcomes (`validation_rules.py`, `validation_rules.yaml`). `src/extraction/table_rules.py` ports both as pure functions with the provenance in its docstring: `classify_table` returns results, descriptive or unknown from the caption and the table's own notes; `is_non_outcome_label` catches Observations, R², Constant, Controls, SD, clusters and similar; `is_descriptive_column` catches columns of means and standard deviations.

Applied to the corpus, with the two fixes it exposed in our own reader:

- Results by caption: 456 tables (28%). Descriptive: 210 (13%). Unknown: 951 (59%), mostly tables with no caption.
- With the extra layouts (a row labelled "Treatment" plus a parenthesised standard-error row, and combined cells on half the rows), an estimate is now found in 521 tables (32%), and a standard error in 353 of them (68%).
- The caption and the reader disagree in two useful ways. In 81 tables the caption says descriptive while the reader read an estimate; inspection shows these are attrition and baseline-mean tables, so the reader over-reads and the caption should veto it. In 189 tables the caption says results while no estimate was read; these are the remaining misses to close.
- Non-outcome rows: 514 of the 10,014 extracted rows (5.1%) carry a non-outcome label, mostly control-group means ("Mean in pure control", 258) and "Constant" (21). An early version also flagged "Average effect of T1" because of the word "average"; that false positive is fixed.

Three behaviours were corrected by testing against the data: classification was reading the surrounding paragraphs (so a nearby "baseline" made a results table look descriptive); the word "matching" made "propensity score matching results" look like a balance table; and the short form "ATT" matched "attrition" because it was a prefix match. Classification now reads only the caption and the table's notes, "matching" and "propensity" are no longer standalone descriptive cues, and short forms must match whole words.

### Inside the table reader

`table_estimates.py` now uses both modules before and after the model call:

- Before the call it computes the table type and the inferred structure. A descriptive table with no estimate inferred is skipped without a model call, and the inferred structure is added to the prompt ("standard error is the column headed 'SE'"), so the model is told what each column is rather than guessing.
- After the call it drops rows whose label is not an outcome (Observations, R², Constant, Controls, means), and marks a table for review when the caption said descriptive but the model still returned estimates. Each table record now carries `skipped`, `non_outcome_rows` and `review`.

Next: close the remaining missed results tables, and measure the reader end to end on a few documents with the structure hint in place.

## A/B result (6 studies, 14 November 2026)

`evaluation/extraction_ab.py` re-extracts a sample with the current reader and scores both the rows already on disk and the new rows against the hand-typed key. Six studies that map to the key:

| | Old rows on disk | New reader |
| --- | --- | --- |
| Estimate value recall | 51 of 84 (61%) | 84 of 84 (100%) |
| SE value recall | 45 of 80 (56%) | 80 of 80 (100%) |
| Rows produced | 1,596 | 3,539 |
| Descriptive tables skipped | 0 | 18 |
| Non-outcome rows dropped | 0 | 26 |

The new reader finds every hand-typed number in the sample, where the old one missed about two in five. That is the coverage gap this work targeted, and it closes it on this sample.

The cost is over-extraction: 2.2 times as many rows. Part of that is better reading of tables the old pipeline under-read, and part is likely duplicates of the same estimate across panels and tables, which the human key keeps once. Because the reader is shown the estimates closest to the question, duplicates waste those slots, so precision and deduplication must be measured before the collection is re-extracted. The change is kept in the pipeline; the collection has not been re-extracted.

Next: deduplicate the new rows (same study, outcome, arm and value), then re-run this A/B on a larger sample before a full re-extraction.

## Derivation and consistency rules

- `t = estimate / se`; `se` from a CI as `(high - low) / (2 * z)` at the stated level; `p` from `t` and df when df is known; stars to a p-bound otherwise.
- `d` from `estimate` and `control_sd` when the outcome is continuous and the scale is known; percent change to log points when the outcome is a share.
- `yi`, `var_d`, `vi`, `se_g` from `d` and the sample sizes per the 8WR `Formula Used` codes (5 and 6), so a row is reproducible against the human sheet.
- Multi-arm tables split into pairwise contrasts against the stated control. Repeated outcomes across tables deduplicate on study, outcome, arm and estimate, keeping the table the text cites. Every derivation writes what it used, so a row can be traced from `literal_cell_text` to `yi`.

## Validation

The human key makes this measurable without new coding: `data/8WR QEX Combined.xlsx` for numbers, and the TVET hand-checks for raw forms. Report per-field precision and recall (estimate, SE, CI, p, N, d, yi) against the key, with a confusion matrix per variant. Run three arms on the same rows: current `table_estimates.py`, OM_QEX v2, and the new normaliser, and keep the one that wins per field. Gate changes on the key the way `evaluation/gate.py` gates answers.

## P0 result (13 November 2026)

`evaluation/normalisation_audit.py` answers the first question with data already on disk, and the answer changes the plan. Where the printed cell contains a standard error, stars, a confidence interval or a p-value, the parser captures it: 0 unparsed of 2,126 parenthesised SEs, 2,748 star rows, 7 interval pairs and 3,196 p-value texts. The parse layer is not the bottleneck.

The bottleneck is extraction coverage and alignment. On the 41 studies that join to the human key by numeric id, our extraction contains the human estimate value (exact match) for 168 of 433 rows (39%) and the SE for 154 of 406 (38%). Matching rows on outcome and arm is unreliable, at 64 of 433, so the per-field agreement numbers (estimate 12 of 64, SE 10 of 52, p 2 of 41, N 6 of 23) mix extraction error with label noise and should not be read as accuracy yet.

So P1 (deterministic parsers) is low value now. The next move is to diagnose the 61% value-recall gap: rounding and units (0.15 against 0.1503), sign conventions, or estimates that sit in tables we did not read. Improving row alignment on study, outcome and arm is the other half, because without it per-field accuracy cannot be measured.

## Staged plan

1. **P0, audit.** Done (`evaluation/normalisation_audit.py`, report in `evaluation/results/`). Parsing is not the gap; value recall is 39% of the human-key rows, and outcome-label alignment is weak.
2. **P1, diagnose value recall.** For a sample of the unmatched human rows, decide whether the value is missed (a table we did not read), rounded or in different units, or the sign differs. Improve alignment on outcome and arm with token overlap. This replaces the parser work.
3. **P2, use the interpreter and derive.** Coverage is measured (28% of tables read as results, 60% of those with an SE). Next, run the interpreter inside `table_estimates.py` before the model call and treat low confidence as a review flag, then implement the derivations `d`, `yi`, `var_d`, `vi`, `se_g` with `formula_used`, and reproduce the 8WR key on its 443 rows.
4. **P3, layouts.** Add the layout detectors (multi-arm, multi-panel, SE-below-row, transposed) and the dedupe and sign rules. Re-run the audit.
5. **P4, validation and gate.** Wire the per-field report into `evaluation/`, publish coverage and accuracy, and gate prompt or parser changes on it.

P0 is the next step and it is cheap: it uses data already on disk. It also tells us whether the gap is parsing (the numbers are present but unread) or extraction (the model did not read the cells), which decides whether P1 or a prompt change comes first.
