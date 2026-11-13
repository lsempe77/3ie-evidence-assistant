# Benchmark graduation_sr_v0.yaml: gate-full_claude-sonnet-5.5 (2026-11-10)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | gate-full_claude-sonnet-5.5 |
| date | 2026-11-10 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.4871 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.559 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.568, 'openai/gpt-6-sol': 0.551} |
| mean_study_claim_score | 0.617 |
| contradicted_claims | 1 |
| must_not_violations | 0 |
| refusal_ok | 2/2 |
| mean_studies_cited | 19.9 |
| mean_seconds | 38.0 |
| openrouter_spend_usd | 0.6925 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 33 | 31/91 | None | 59.1 |
| grad-002 | synthesis | 0.417 | 0 | 44 | 40/91 | None | 46.8 |
| grad-003 | synthesis | 0.417 | 1 | 26 | 24/91 | None | 48.3 |
| grad-004 | synthesis | 0.583 | 0 | 31 | 30/91 | None | 47.8 |
| grad-005 | synthesis | 0.0 | 0 | 14 | 14/91 | None | 39.6 |
| grad-006 | synthesis | 0.5 | 0 | 29 | 28/91 | None | 42.2 |
| grad-007 | implementation | 0.6 | 0 | 21 | - | None | 37.7 |
| grad-008 | implementation | 0.583 | 0 | 26 | - | None | 41.3 |
| grad-009 | implementation | 0.75 | 0 | 29 | - | None | 38.6 |
| grad-010 | cost | 0.5 | 0 | 21 | - | None | 36.2 |
| grad-011 | cost | 0.375 | 0 | 16 | - | None | 37.1 |
| grad-012 | country | 0.5 | 0 | 2 | - | None | 25.2 |
| grad-013 | country | 0.5 | 0 | 3 | 1/1 | None | 25.4 |
| grad-014 | country | 0.167 | 0 | 1 | 1/1 | None | 24.7 |
| grad-015 | synthesis | 0.667 | 0 | 37 | 34/91 | None | 34.6 |
| grad-016 | gap | 1.0 | 0 | 2 | - | True | 31.6 |
| grad-017 | gap | 1.0 | 0 | 16 | - | True | 33.5 |
| grad-018 | gap | 0.375 | 0 | 23 | - | None | 38.8 |
| grad-019 | multilingual | 1.0 | 0 | 5 | 2/3 | None | 33.5 |
| grad-020 | synthesis | 0.5 | 0 | 19 | 17/91 | None | 38.0 |
