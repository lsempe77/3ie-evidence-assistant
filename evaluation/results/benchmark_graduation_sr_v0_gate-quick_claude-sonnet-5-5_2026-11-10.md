# Benchmark graduation_sr_v0.yaml: gate-quick_claude-sonnet-5.5 (2026-11-10)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | gate-quick_claude-sonnet-5.5 |
| date | 2026-11-10 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.0828 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 5 |
| errors | 0 |
| mean_claim_score | 0.651 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.7, 'openai/gpt-6-sol': 0.602} |
| mean_study_claim_score | 0.663 |
| contradicted_claims | 0 |
| must_not_violations | 1 |
| refusal_ok | 1/1 |
| mean_studies_cited | 15.4 |
| mean_seconds | 26.0 |
| openrouter_spend_usd | 0.1419 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-002 | synthesis | 0.417 | 0 | 37 | 34/91 | None | 34.1 |
| grad-007 | implementation | 0.4 | 0 | 17 | - | None | 26.5 |
| grad-011 | cost | 0.438 | 0 | 15 | - | None | 29.5 |
| grad-016 | gap | 1.0 | 0 | 3 | - | True | 18.9 |
| grad-019 | multilingual | 1.0 | 0 | 5 | 2/3 | None | 20.8 |
