# Benchmark graduation_sr_v0.yaml: current-app-2judges (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | current-app-2judges |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| rejudged_from | benchmark_graduation_sr_v0_after-fixes_2026-11-09.json |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.289 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.3, 'openai/gpt-6-sol': 0.278} |
| mean_study_claim_score | 0.307 |
| contradicted_claims | 1 |
| must_not_violations | 2 |
| refusal_ok | 0/2 |
| mean_studies_cited | 8.7 |
| mean_seconds | 32.4 |
| openrouter_spend_usd | 0.2399 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.25 | 0 | 10 | 10/91 | None | 50.6 |
| grad-002 | synthesis | 0.417 | 0 | 10 | 10/91 | None | 30.8 |
| grad-003 | synthesis | 0.0 | 1 | 10 | 9/91 | None | 29.7 |
| grad-004 | synthesis | 0.25 | 0 | 10 | 10/91 | None | 29.2 |
| grad-005 | synthesis | 0.0 | 0 | 10 | 9/91 | None | 29.0 |
| grad-006 | synthesis | 0.5 | 0 | 10 | 9/91 | None | 35.3 |
| grad-007 | implementation | 0.3 | 0 | 10 | - | None | 33.2 |
| grad-008 | implementation | 0.167 | 0 | 10 | - | None | 27.5 |
| grad-009 | implementation | 0.25 | 0 | 7 | - | None | 34.0 |
| grad-010 | cost | 0.25 | 0 | 10 | - | None | 32.6 |
| grad-011 | cost | 0.0 | 0 | 10 | - | None | 35.9 |
| grad-012 | country | 0.5 | 0 | 3 | - | None | 23.8 |
| grad-013 | country | 0.167 | 0 | 6 | 1/1 | None | 26.2 |
| grad-014 | country | 0.167 | 0 | 5 | 1/1 | None | 27.7 |
| grad-015 | synthesis | 0.5 | 0 | 10 | 7/91 | None | 28.0 |
| grad-016 | gap | 0.75 | 0 | 10 | - | False | 27.7 |
| grad-017 | gap | 0.0 | 0 | 10 | - | False | 61.9 |
| grad-018 | gap | 0.062 | 0 | 10 | - | None | 34.7 |
| grad-019 | multilingual | 0.75 | 0 | 2 | 2/3 | None | 23.4 |
| grad-020 | synthesis | 0.5 | 0 | 10 | 9/91 | None | 27.4 |
