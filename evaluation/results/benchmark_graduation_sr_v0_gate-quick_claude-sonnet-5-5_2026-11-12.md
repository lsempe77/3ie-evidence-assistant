# Benchmark graduation_sr_v0.yaml: gate-quick_claude-sonnet-5.5 (2026-11-12)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | gate-quick_claude-sonnet-5.5 |
| date | 2026-11-12 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.1308 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 5 |
| errors | 0 |
| mean_claim_score | 0.677 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.703, 'openai/gpt-6-sol': 0.65} |
| mean_study_claim_score | 0.652 |
| contradicted_claims | 0 |
| must_not_violations | 1 |
| refusal_ok | 1/1 |
| mean_studies_cited | 16.8 |
| mean_seconds | 43.2 |
| openrouter_spend_usd | 0.162 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-002 | synthesis | 0.583 | 0 | 30 | 29/91 | None | 54.6 |
| grad-007 | implementation | 0.55 | 0 | 30 | - | None | 40.8 |
| grad-011 | cost | 0.25 | 0 | 19 | - | None | 43.4 |
| grad-016 | gap | 1.0 | 0 | 2 | - | True | 39.7 |
| grad-019 | multilingual | 1.0 | 0 | 3 | 2/3 | None | 37.4 |
