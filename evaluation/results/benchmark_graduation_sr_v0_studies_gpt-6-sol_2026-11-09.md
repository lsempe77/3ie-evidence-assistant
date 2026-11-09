# Benchmark graduation_sr_v0.yaml: studies_gpt-6-sol (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studies_gpt-6-sol |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | openai/gpt-6-sol |
| reading_spend_usd_shared | 0.4621 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.503 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.518, 'openai/gpt-6-sol': 0.487} |
| mean_study_claim_score | 0.554 |
| contradicted_claims | 0 |
| must_not_violations | 0 |
| refusal_ok | 1/1 |
| mean_studies_cited | 7.9 |
| mean_seconds | 24.7 |
| openrouter_spend_usd | 0.4319 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.625 | 0 | 19 | 19/91 | None | 34.7 |
| grad-002 | synthesis | 0.5 | 0 | 15 | 15/91 | None | 31.9 |
| grad-003 | synthesis | 0.583 | 0 | 6 | 5/91 | None | 29.4 |
| grad-004 | synthesis | 0.667 | 0 | 9 | 9/91 | None | 27.9 |
| grad-005 | synthesis | 0.25 | 0 | 3 | 3/91 | None | 25.3 |
| grad-006 | synthesis | 0.75 | 0 | 8 | 8/91 | None | 34.2 |
| grad-007 | implementation | 0.2 | 0 | 9 | - | None | 30.9 |
| grad-008 | implementation | 0.167 | 0 | 8 | - | None | 23.1 |
| grad-009 | implementation | 0.75 | 0 | 12 | - | None | 26.0 |
| grad-010 | cost | 0.25 | 0 | 13 | - | None | 23.1 |
| grad-011 | cost | 0.25 | 0 | 7 | - | None | 27.8 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 16.5 |
| grad-013 | country | 0.5 | 0 | 2 | 0/1 | None | 16.8 |
| grad-014 | country | 0.5 | 0 | 2 | 1/1 | None | 15.7 |
| grad-015 | synthesis | 0.5 | 0 | 16 | 14/91 | None | 28.6 |
| grad-016 | gap | 1.0 | 0 | 1 | - | True | 20.3 |
| grad-017 | gap | 0.5 | 0 | 7 | - | None | 19.2 |
| grad-018 | gap | 0.312 | 0 | 12 | - | None | 26.7 |
| grad-019 | multilingual | 1.0 | 0 | 1 | 1/3 | None | 12.1 |
| grad-020 | synthesis | 0.5 | 0 | 6 | 5/91 | None | 23.3 |
