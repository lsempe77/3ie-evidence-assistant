# Benchmark graduation_sr_v0.yaml: studies_claude-sonnet-5.5 (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studies_claude-sonnet-5.5 |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.4621 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.494 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.517, 'openai/gpt-6-sol': 0.471} |
| mean_study_claim_score | 0.558 |
| contradicted_claims | 1 |
| must_not_violations | 0 |
| refusal_ok | 2/2 |
| mean_studies_cited | 10.1 |
| mean_seconds | 25.2 |
| openrouter_spend_usd | 0.4251 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 20 | 19/91 | None | 36.0 |
| grad-002 | synthesis | 0.583 | 0 | 25 | 23/91 | None | 25.5 |
| grad-003 | synthesis | 0.417 | 0 | 12 | 11/91 | None | 28.5 |
| grad-004 | synthesis | 0.75 | 0 | 14 | 13/91 | None | 29.0 |
| grad-005 | synthesis | 0.0 | 0 | 3 | 3/91 | None | 27.6 |
| grad-006 | synthesis | 0.5 | 0 | 18 | 16/91 | None | 37.4 |
| grad-007 | implementation | 0.3 | 0 | 9 | - | None | 33.9 |
| grad-008 | implementation | 0.167 | 0 | 8 | - | None | 21.7 |
| grad-009 | implementation | 0.625 | 0 | 13 | - | None | 25.7 |
| grad-010 | cost | 0.25 | 1 | 13 | - | None | 23.2 |
| grad-011 | cost | 0.125 | 0 | 7 | - | None | 25.1 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 17.2 |
| grad-013 | country | 0.5 | 0 | 2 | 0/1 | None | 16.8 |
| grad-014 | country | 0.5 | 0 | 2 | 1/1 | None | 18.5 |
| grad-015 | synthesis | 0.667 | 0 | 17 | 15/91 | None | 25.3 |
| grad-016 | gap | 1.0 | 0 | 1 | - | True | 21.8 |
| grad-017 | gap | 0.75 | 0 | 10 | - | True | 20.8 |
| grad-018 | gap | 0.25 | 0 | 12 | - | None | 28.0 |
| grad-019 | multilingual | 1.0 | 0 | 1 | 1/3 | None | 16.3 |
| grad-020 | synthesis | 0.5 | 0 | 12 | 11/91 | None | 25.4 |
