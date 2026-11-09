# Benchmark graduation_sr_v0.yaml: studies_gemini-3.8-flash (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studies_gemini-3.8-flash |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | google/gemini-3.8-flash |
| reading_spend_usd_shared | 0.4621 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.484 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.498, 'openai/gpt-6-sol': 0.47} |
| mean_study_claim_score | 0.548 |
| contradicted_claims | 2 |
| must_not_violations | 1 |
| refusal_ok | 1/2 |
| mean_studies_cited | 9.7 |
| mean_seconds | 38.0 |
| openrouter_spend_usd | 0.3357 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 14 | 13/91 | None | 56.7 |
| grad-002 | synthesis | 0.5 | 0 | 25 | 23/91 | None | 34.6 |
| grad-003 | synthesis | 0.333 | 1 | 11 | 10/91 | None | 34.8 |
| grad-004 | synthesis | 0.667 | 0 | 14 | 13/91 | None | 59.7 |
| grad-005 | synthesis | 0.0 | 0 | 3 | 3/91 | None | 28.2 |
| grad-006 | synthesis | 1.0 | 0 | 17 | 16/91 | None | 43.8 |
| grad-007 | implementation | 0.2 | 0 | 9 | - | None | 52.1 |
| grad-008 | implementation | 0.25 | 0 | 8 | - | None | 43.6 |
| grad-009 | implementation | 0.375 | 0 | 13 | - | None | 45.9 |
| grad-010 | cost | 0.25 | 1 | 13 | - | None | 43.0 |
| grad-011 | cost | 0.188 | 0 | 7 | - | None | 44.9 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 23.6 |
| grad-013 | country | 0.5 | 0 | 2 | 0/1 | None | 38.2 |
| grad-014 | country | 0.5 | 0 | 2 | 1/1 | None | 35.8 |
| grad-015 | synthesis | 0.667 | 0 | 17 | 15/91 | None | 33.4 |
| grad-016 | gap | 1.0 | 0 | 1 | - | True | 27.6 |
| grad-017 | gap | 0.5 | 0 | 10 | - | False | 28.0 |
| grad-018 | gap | 0.25 | 0 | 12 | - | None | 35.4 |
| grad-019 | multilingual | 1.0 | 0 | 1 | 1/3 | None | 19.1 |
| grad-020 | synthesis | 0.5 | 0 | 12 | 11/91 | None | 32.3 |
