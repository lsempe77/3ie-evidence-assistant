# Benchmark graduation_sr_v0.yaml: studies_claude-haiku-5.5 (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studies_claude-haiku-5.5 |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-haiku-5.5 |
| reading_spend_usd_shared | 0.4621 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.491 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.514, 'openai/gpt-6-sol': 0.468} |
| mean_study_claim_score | 0.543 |
| contradicted_claims | 0 |
| must_not_violations | 0 |
| refusal_ok | 2/2 |
| mean_studies_cited | 9.9 |
| mean_seconds | 26.4 |
| openrouter_spend_usd | 0.2814 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 19 | 18/91 | None | 37.6 |
| grad-002 | synthesis | 0.583 | 0 | 25 | 23/91 | None | 25.6 |
| grad-003 | synthesis | 0.417 | 0 | 12 | 11/91 | None | 30.8 |
| grad-004 | synthesis | 0.583 | 0 | 14 | 13/91 | None | 31.1 |
| grad-005 | synthesis | 0.0 | 0 | 3 | 3/91 | None | 27.4 |
| grad-006 | synthesis | 0.5 | 0 | 18 | 16/91 | None | 34.0 |
| grad-007 | implementation | 0.2 | 0 | 9 | - | None | 31.6 |
| grad-008 | implementation | 0.333 | 0 | 8 | - | None | 23.7 |
| grad-009 | implementation | 0.625 | 0 | 13 | - | None | 26.6 |
| grad-010 | cost | 0.5 | 0 | 13 | - | None | 25.3 |
| grad-011 | cost | 0.25 | 0 | 7 | - | None | 28.4 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 19.8 |
| grad-013 | country | 0.5 | 0 | 2 | 0/1 | None | 19.2 |
| grad-014 | country | 0.333 | 0 | 2 | 1/1 | None | 18.6 |
| grad-015 | synthesis | 0.5 | 0 | 17 | 15/91 | None | 29.9 |
| grad-016 | gap | 1.0 | 0 | 1 | - | True | 21.6 |
| grad-017 | gap | 0.75 | 0 | 9 | - | True | 21.0 |
| grad-018 | gap | 0.25 | 0 | 12 | - | None | 32.3 |
| grad-019 | multilingual | 1.0 | 0 | 1 | 1/3 | None | 15.5 |
| grad-020 | synthesis | 0.5 | 0 | 11 | 10/91 | None | 27.0 |
