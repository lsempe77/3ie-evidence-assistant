# Benchmark graduation_sr_v0.yaml: gate-full_claude-sonnet-5.5 (2026-11-11)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | gate-full_claude-sonnet-5.5 |
| date | 2026-11-11 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.4892 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.545 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.565, 'openai/gpt-6-sol': 0.525} |
| mean_study_claim_score | 0.592 |
| contradicted_claims | 2 |
| must_not_violations | 0 |
| refusal_ok | 2/2 |
| mean_studies_cited | 19.1 |
| mean_seconds | 37.4 |
| openrouter_spend_usd | 0.7655 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 36 | 34/91 | None | 42.7 |
| grad-002 | synthesis | 0.667 | 0 | 33 | 32/91 | None | 42.6 |
| grad-003 | synthesis | 0.25 | 1 | 26 | 26/91 | None | 39.5 |
| grad-004 | synthesis | 0.667 | 0 | 33 | 31/91 | None | 39.0 |
| grad-005 | synthesis | 0.0 | 0 | 11 | 11/91 | None | 37.5 |
| grad-006 | synthesis | 1.0 | 0 | 31 | 31/91 | None | 34.5 |
| grad-007 | implementation | 0.45 | 0 | 20 | - | None | 34.3 |
| grad-008 | implementation | 0.583 | 0 | 26 | - | None | 43.3 |
| grad-009 | implementation | 0.625 | 0 | 30 | - | None | 42.2 |
| grad-010 | cost | 0.375 | 1 | 19 | - | None | 36.2 |
| grad-011 | cost | 0.5 | 0 | 17 | - | None | 35.1 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 30.0 |
| grad-013 | country | 0.5 | 0 | 3 | 1/1 | None | 33.5 |
| grad-014 | country | 0.167 | 0 | 1 | 1/1 | None | 34.3 |
| grad-015 | synthesis | 0.5 | 0 | 39 | 37/91 | None | 41.8 |
| grad-016 | gap | 1.0 | 0 | 1 | - | True | 34.3 |
| grad-017 | gap | 0.75 | 0 | 14 | - | True | 39.3 |
| grad-018 | gap | 0.375 | 0 | 21 | - | None | 38.6 |
| grad-019 | multilingual | 1.0 | 0 | 4 | 2/3 | None | 31.3 |
| grad-020 | synthesis | 0.5 | 0 | 14 | 12/91 | None | 37.4 |
