# Benchmark graduation_sr_v0.yaml: studies_deepseek-v4.1-flash (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studies_deepseek-v4.1-flash |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | deepseek/deepseek-v4.1-flash |
| reading_spend_usd_shared | 0.4621 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.474 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.513, 'openai/gpt-6-sol': 0.435} |
| mean_study_claim_score | 0.521 |
| contradicted_claims | 0 |
| must_not_violations | 1 |
| refusal_ok | 2/2 |
| mean_studies_cited | 9.9 |
| mean_seconds | 34.9 |
| openrouter_spend_usd | 0.2247 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 19 | 18/91 | None | 36.2 |
| grad-002 | synthesis | 0.5 | 0 | 24 | 22/91 | None | 37.3 |
| grad-003 | synthesis | 0.417 | 0 | 12 | 11/91 | None | 39.9 |
| grad-004 | synthesis | 0.667 | 0 | 14 | 13/91 | None | 30.0 |
| grad-005 | synthesis | 0.0 | 0 | 3 | 3/91 | None | 30.6 |
| grad-006 | synthesis | 0.5 | 0 | 17 | 15/91 | None | 41.9 |
| grad-007 | implementation | 0.25 | 0 | 9 | - | None | 33.7 |
| grad-008 | implementation | 0.167 | 0 | 8 | - | None | 42.0 |
| grad-009 | implementation | 0.625 | 0 | 13 | - | None | 38.7 |
| grad-010 | cost | 0.5 | 0 | 13 | - | None | 31.8 |
| grad-011 | cost | 0.188 | 0 | 7 | - | None | 57.3 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 17.8 |
| grad-013 | country | 0.5 | 0 | 2 | 0/1 | None | 20.0 |
| grad-014 | country | 0.417 | 0 | 2 | 1/1 | None | 20.3 |
| grad-015 | synthesis | 0.5 | 0 | 17 | 15/91 | None | 58.6 |
| grad-016 | gap | 1.0 | 0 | 1 | - | True | 32.1 |
| grad-017 | gap | 0.75 | 0 | 10 | - | True | 31.2 |
| grad-018 | gap | 0.25 | 0 | 12 | - | None | 43.4 |
| grad-019 | multilingual | 1.0 | 0 | 1 | 1/3 | None | 22.5 |
| grad-020 | synthesis | 0.25 | 0 | 12 | 11/91 | None | 31.8 |
