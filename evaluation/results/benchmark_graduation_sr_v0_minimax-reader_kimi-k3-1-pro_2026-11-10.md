# Benchmark graduation_sr_v0.yaml: minimax-reader_kimi-k3.1-pro (2026-11-10)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | minimax-reader_kimi-k3.1-pro |
| date | 2026-11-10 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | minimax/minimax-m3.1-flash |
| answer_model | moonshotai/kimi-k3.1-pro |
| reading_spend_usd_shared | 0.236 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.573 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.584, 'openai/gpt-6-sol': 0.561} |
| mean_study_claim_score | 0.635 |
| contradicted_claims | 4 |
| must_not_violations | 1 |
| refusal_ok | 1/2 |
| mean_studies_cited | 13.3 |
| mean_seconds | 35.8 |
| openrouter_spend_usd | 0.6063 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 16 | 15/91 | None | 52.3 |
| grad-002 | synthesis | 0.5 | 0 | 22 | 20/91 | None | 49.3 |
| grad-003 | synthesis | 0.167 | 2 | 15 | 14/91 | None | 34.5 |
| grad-004 | synthesis | 0.75 | 0 | 19 | 17/91 | None | 35.4 |
| grad-005 | synthesis | 0.0 | 1 | 11 | 11/91 | None | 29.4 |
| grad-006 | synthesis | 1.0 | 0 | 22 | 22/91 | None | 54.4 |
| grad-007 | implementation | 0.6 | 0 | 18 | - | None | 23.7 |
| grad-008 | implementation | 0.75 | 0 | 17 | - | None | 32.7 |
| grad-009 | implementation | 0.75 | 0 | 20 | - | None | 33.0 |
| grad-010 | cost | 0.25 | 1 | 19 | - | None | 25.0 |
| grad-011 | cost | 0.438 | 0 | 13 | - | None | 62.4 |
| grad-012 | country | 0.5 | 0 | 2 | - | None | 20.8 |
| grad-013 | country | 0.667 | 0 | 3 | 1/1 | None | 13.4 |
| grad-014 | country | 0.167 | 0 | 2 | 1/1 | None | 28.1 |
| grad-015 | synthesis | 0.667 | 0 | 21 | 20/91 | None | 59.7 |
| grad-016 | gap | 1.0 | 0 | 0 | - | True | 27.7 |
| grad-017 | gap | 0.5 | 0 | 11 | - | False | 24.1 |
| grad-018 | gap | 0.5 | 0 | 17 | - | None | 38.5 |
| grad-019 | multilingual | 1.0 | 0 | 5 | 2/3 | None | 27.2 |
| grad-020 | synthesis | 0.5 | 0 | 13 | 11/91 | None | 44.0 |
