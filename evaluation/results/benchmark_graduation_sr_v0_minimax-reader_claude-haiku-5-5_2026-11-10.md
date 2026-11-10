# Benchmark graduation_sr_v0.yaml: minimax-reader_claude-haiku-5.5 (2026-11-10)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | minimax-reader_claude-haiku-5.5 |
| date | 2026-11-10 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | minimax/minimax-m3.1-flash |
| answer_model | anthropic/claude-haiku-5.5 |
| reading_spend_usd_shared | 0.236 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.483 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.496, 'openai/gpt-6-sol': 0.47} |
| mean_study_claim_score | 0.539 |
| contradicted_claims | 3 |
| must_not_violations | 1 |
| refusal_ok | 2/2 |
| mean_studies_cited | 14.1 |
| mean_seconds | 32.2 |
| openrouter_spend_usd | 0.2517 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.5 | 0 | 24 | 24/91 | None | 49.2 |
| grad-002 | synthesis | 0.417 | 0 | 19 | 17/91 | None | 39.1 |
| grad-003 | synthesis | 0.333 | 1 | 22 | 21/91 | None | 41.0 |
| grad-004 | synthesis | 0.583 | 0 | 26 | 25/91 | None | 33.7 |
| grad-005 | synthesis | 0.0 | 1 | 11 | 11/91 | None | 30.4 |
| grad-006 | synthesis | 0.5 | 0 | 18 | 18/91 | None | 32.2 |
| grad-007 | implementation | 0.45 | 0 | 19 | - | None | 31.3 |
| grad-008 | implementation | 0.417 | 0 | 16 | - | None | 31.7 |
| grad-009 | implementation | 0.625 | 0 | 21 | - | None | 29.3 |
| grad-010 | cost | 0.25 | 1 | 16 | - | None | 30.2 |
| grad-011 | cost | 0.375 | 0 | 13 | - | None | 40.3 |
| grad-012 | country | 0.5 | 0 | 2 | - | None | 21.3 |
| grad-013 | country | 0.583 | 0 | 3 | 1/1 | None | 15.5 |
| grad-014 | country | 0.25 | 0 | 2 | 1/1 | None | 19.5 |
| grad-015 | synthesis | 0.5 | 0 | 22 | 21/91 | None | 40.4 |
| grad-016 | gap | 1.0 | 0 | 0 | - | True | 29.5 |
| grad-017 | gap | 0.5 | 0 | 11 | - | True | 26.2 |
| grad-018 | gap | 0.375 | 0 | 16 | - | None | 39.1 |
| grad-019 | multilingual | 1.0 | 0 | 5 | 2/3 | None | 28.0 |
| grad-020 | synthesis | 0.5 | 0 | 16 | 14/91 | None | 35.4 |
