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
3. **P2, parsers and derivations.** With recall understood, implement the deterministic parsers for the variants that remain, then `d`, `yi`, `var_d`, `vi`, `se_g` with `formula_used`, and reproduce the 8WR key on its 443 rows.
4. **P3, layouts.** Add the layout detectors (multi-arm, multi-panel, SE-below-row, transposed) and the dedupe and sign rules. Re-run the audit.
5. **P4, validation and gate.** Wire the per-field report into `evaluation/`, publish coverage and accuracy, and gate prompt or parser changes on it.

P0 is the next step and it is cheap: it uses data already on disk. It also tells us whether the gap is parsing (the numbers are present but unread) or extraction (the model did not read the cells), which decides whether P1 or a prompt change comes first.
