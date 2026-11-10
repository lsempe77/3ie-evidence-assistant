# Benchmark graduation_sr_v0.yaml: minimax-reader_claude-sonnet-5.5 (2026-11-10)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | minimax-reader_claude-sonnet-5.5 |
| date | 2026-11-10 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | minimax/minimax-m3.1-flash |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.236 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.559 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.59, 'openai/gpt-6-sol': 0.528} |
| mean_study_claim_score | 0.618 |
| contradicted_claims | 2 |
| must_not_violations | 1 |
| refusal_ok | 2/2 |
| mean_studies_cited | 16.8 |
| mean_seconds | 27.4 |
| openrouter_spend_usd | 0.6143 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 27 | 26/91 | None | 39.2 |
| grad-002 | synthesis | 0.417 | 0 | 32 | 28/91 | None | 33.0 |
| grad-003 | synthesis | 0.333 | 1 | 26 | 24/91 | None | 31.8 |
| grad-004 | synthesis | 0.75 | 0 | 29 | 28/91 | None | 29.8 |
| grad-005 | synthesis | 0.0 | 0 | 11 | 11/91 | None | 24.2 |
| grad-006 | synthesis | 0.75 | 0 | 25 | 25/91 | None | 26.0 |
| grad-007 | implementation | 0.6 | 0 | 19 | - | None | 25.9 |
| grad-008 | implementation | 0.583 | 0 | 19 | - | None | 23.8 |
| grad-009 | implementation | 0.625 | 0 | 23 | - | None | 22.9 |
| grad-010 | cost | 0.375 | 1 | 21 | - | None | 23.3 |
| grad-011 | cost | 0.562 | 0 | 14 | - | None | 37.5 |
| grad-012 | country | 0.5 | 0 | 2 | - | None | 23.1 |
| grad-013 | country | 0.667 | 0 | 3 | 1/1 | None | 15.4 |
| grad-014 | country | 0.167 | 0 | 2 | 1/1 | None | 14.7 |
| grad-015 | synthesis | 0.667 | 0 | 31 | 30/91 | None | 35.7 |
| grad-016 | gap | 1.0 | 0 | 0 | - | True | 31.4 |
| grad-017 | gap | 0.5 | 0 | 12 | - | True | 23.8 |
| grad-018 | gap | 0.438 | 0 | 18 | - | None | 34.5 |
| grad-019 | multilingual | 1.0 | 0 | 5 | 2/3 | None | 26.0 |
| grad-020 | synthesis | 0.5 | 0 | 16 | 14/91 | None | 26.5 |
