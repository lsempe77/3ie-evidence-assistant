# Benchmark graduation_sr_v0.yaml: studies_gpt-4o (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studies_gpt-4o |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | openai/gpt-4o |
| reading_spend_usd_shared | 0.4621 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.486 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.561, 'openai/gpt-6-sol': 0.434} |
| mean_study_claim_score | 0.543 |
| contradicted_claims | 0 |
| must_not_violations | 0 |
| refusal_ok | 2/2 |
| mean_studies_cited | 8.1 |
| mean_seconds | 22.0 |
| openrouter_spend_usd | 0.3082 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.625 | 0 | 10 | 10/91 | None | 30.6 |
| grad-002 | synthesis | 0.583 | 0 | 25 | 23/91 | None | 20.2 |
| grad-003 | synthesis | 0.333 | 0 | 9 | 8/91 | None | 24.8 |
| grad-004 | synthesis | 0.75 | 0 | 10 | 10/91 | None | 28.8 |
| grad-005 | synthesis | 0.0 | 0 | 3 | 3/91 | None | 21.9 |
| grad-006 | synthesis | 0.5 | 0 | 10 | 10/91 | None | 30.6 |
| grad-007 | implementation | 0.35 | 0 | 8 | - | None | 28.1 |
| grad-008 | implementation | 0.25 | 0 | 8 | - | None | 20.2 |
| grad-009 | implementation | 0.625 | 0 | 11 | - | None | 21.8 |
| grad-010 | cost | 0.25 | 0 | 8 | - | None | 19.6 |
| grad-011 | cost | 0.125 | 0 | 6 | - | None | 22.5 |
| grad-012 | country | 0.25 | 0 | 2 | - | None | 16.6 |
| grad-013 | country | 0.5 | 0 | 2 | 0/1 | None | 17.2 |
| grad-014 | country | 0.333 | 0 | 2 | 1/1 | None | 15.4 |
| grad-015 | synthesis | 0.5 | 0 | 15 | 13/91 | None | 22.8 |
| grad-016 | gap | 1.0 | 0 | 1 | - | True | 18.2 |
| grad-017 | gap | 0.75 | 0 | 8 | - | True | 17.2 |
| grad-018 | gap | 0.25 | 0 | 12 | - | None | 26.3 |
| grad-019 | multilingual | 1.0 | 0 | 1 | 1/3 | None | 13.5 |
| grad-020 | synthesis | 0.75 | 0 | 10 | 9/91 | None | 24.1 |
