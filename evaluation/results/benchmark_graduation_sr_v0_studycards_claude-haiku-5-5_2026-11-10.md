# Benchmark graduation_sr_v0.yaml: studycards_claude-haiku-5.5 (2026-11-10)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studycards_claude-haiku-5.5 |
| date | 2026-11-10 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-haiku-5.5 |
| reading_spend_usd_shared | 0.3521 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.517 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.545, 'openai/gpt-6-sol': 0.489} |
| mean_study_claim_score | 0.558 |
| contradicted_claims | 3 |
| must_not_violations | 1 |
| refusal_ok | 2/2 |
| mean_studies_cited | 14.2 |
| mean_seconds | 38.7 |
| openrouter_spend_usd | 0.2691 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 20 | 19/91 | None | 74.4 |
| grad-002 | synthesis | 0.667 | 0 | 23 | 22/91 | None | 56.0 |
| grad-003 | synthesis | 0.25 | 1 | 16 | 15/91 | None | 43.7 |
| grad-004 | synthesis | 0.5 | 1 | 22 | 21/91 | None | 46.5 |
| grad-005 | synthesis | 0.0 | 0 | 11 | 11/91 | None | 36.1 |
| grad-006 | synthesis | 0.5 | 0 | 14 | 13/91 | None | 34.3 |
| grad-007 | implementation | 0.4 | 0 | 15 | - | None | 32.2 |
| grad-008 | implementation | 0.667 | 0 | 22 | - | None | 35.9 |
| grad-009 | implementation | 0.5 | 0 | 23 | - | None | 47.5 |
| grad-010 | cost | 0.5 | 0 | 18 | - | None | 36.0 |
| grad-011 | cost | 0.375 | 1 | 13 | - | None | 40.3 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 24.1 |
| grad-013 | country | 0.5 | 0 | 2 | 0/1 | None | 20.8 |
| grad-014 | country | 0.25 | 0 | 2 | 1/1 | None | 19.8 |
| grad-015 | synthesis | 0.667 | 0 | 31 | 30/91 | None | 42.1 |
| grad-016 | gap | 1.0 | 0 | 3 | - | True | 32.7 |
| grad-017 | gap | 0.75 | 0 | 14 | - | True | 32.8 |
| grad-018 | gap | 0.312 | 0 | 15 | - | None | 48.6 |
| grad-019 | multilingual | 1.0 | 0 | 4 | 2/3 | None | 38.5 |
| grad-020 | synthesis | 0.5 | 0 | 14 | 12/91 | None | 32.2 |
