# Benchmark graduation_sr_v0.yaml: gate-full_claude-sonnet-5.5 (2026-11-11)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | gate-full_claude-sonnet-5.5 |
| date | 2026-11-11 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.5078 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.564 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.578, 'openai/gpt-6-sol': 0.551} |
| mean_study_claim_score | 0.578 |
| contradicted_claims | 1 |
| must_not_violations | 0 |
| refusal_ok | 2/2 |
| mean_studies_cited | 15.8 |
| mean_seconds | 44.8 |
| openrouter_spend_usd | 0.8503 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.625 | 0 | 26 | 26/91 | None | 57.6 |
| grad-002 | synthesis | 0.75 | 0 | 38 | 37/91 | None | 57.2 |
| grad-003 | synthesis | 0.25 | 1 | 30 | 30/91 | None | 51.4 |
| grad-004 | synthesis | 0.583 | 0 | 25 | 24/91 | None | 46.6 |
| grad-005 | synthesis | 0.5 | 0 | 12 | 12/91 | None | 44.2 |
| grad-006 | synthesis | 0.5 | 0 | 28 | 28/91 | None | 44.6 |
| grad-007 | implementation | 0.35 | 0 | 17 | - | None | 41.4 |
| grad-008 | implementation | 0.583 | 0 | 24 | - | None | 41.4 |
| grad-009 | implementation | 0.5 | 0 | 21 | - | None | 48.0 |
| grad-010 | cost | 0.5 | 0 | 19 | - | None | 39.2 |
| grad-011 | cost | 0.5 | 0 | 10 | - | None | 44.9 |
| grad-012 | country | 0.5 | 0 | 1 | - | None | 33.3 |
| grad-013 | country | 0.5 | 0 | 2 | 1/1 | None | 32.4 |
| grad-014 | country | 0.083 | 0 | 1 | 1/1 | None | 43.5 |
| grad-015 | synthesis | 0.5 | 0 | 20 | 20/91 | None | 51.5 |
| grad-016 | gap | 1.0 | 0 | 3 | - | True | 44.4 |
| grad-017 | gap | 1.0 | 0 | 12 | - | True | 46.2 |
| grad-018 | gap | 0.562 | 0 | 9 | - | None | 44.7 |
| grad-019 | multilingual | 1.0 | 0 | 3 | 2/3 | None | 35.4 |
| grad-020 | synthesis | 0.5 | 0 | 15 | 14/91 | None | 47.9 |
