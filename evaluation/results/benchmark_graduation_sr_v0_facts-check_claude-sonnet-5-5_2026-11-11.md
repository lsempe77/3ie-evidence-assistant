# Benchmark graduation_sr_v0.yaml: facts-check_claude-sonnet-5.5 (2026-11-11)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | facts-check_claude-sonnet-5.5 |
| date | 2026-11-11 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.0187 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 2 |
| errors | 0 |
| mean_claim_score | 0.375 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.312, 'openai/gpt-6-sol': 0.438} |
| mean_study_claim_score | 0.375 |
| contradicted_claims | 1 |
| must_not_violations | 0 |
| refusal_ok | 0/0 |
| mean_studies_cited | 16.0 |
| mean_seconds | 39.5 |
| openrouter_spend_usd | 0.0323 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-010 | cost | 0.375 | 1 | 17 | - | None | 38.8 |
| grad-011 | cost | 0.375 | 0 | 15 | - | None | 40.1 |
