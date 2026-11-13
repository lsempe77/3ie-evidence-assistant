# Benchmark graduation_sr_v0.yaml: studies-smoke_claude-sonnet-5.5 (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | studies-smoke_claude-sonnet-5.5 |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.0142 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 2 |
| errors | 0 |
| mean_claim_score | 0.208 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.167, 'openai/gpt-6-sol': 0.25} |
| contradicted_claims | 0 |
| must_not_violations | 0 |
| refusal_ok | 0/0 |
| mean_studies_cited | 7.0 |
| mean_seconds | 24.4 |
| openrouter_spend_usd | 0.0483 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-003 | synthesis | 0.417 | 0 | 10 | 9/91 | None | 26.9 |
| grad-005 | synthesis | 0.0 | 0 | 4 | 4/91 | None | 21.8 |
