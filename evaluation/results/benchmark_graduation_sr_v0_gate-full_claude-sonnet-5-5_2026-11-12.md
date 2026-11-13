# Benchmark graduation_sr_v0.yaml: gate-full_claude-sonnet-5.5 (2026-11-12)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | gate-full_claude-sonnet-5.5 |
| date | 2026-11-12 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| pipeline | studies |
| reader_model | anthropic/claude-haiku-5.5 |
| answer_model | anthropic/claude-sonnet-5.5 |
| reading_spend_usd_shared | 0.5414 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.567 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.571, 'openai/gpt-6-sol': 0.563} |
| mean_study_claim_score | 0.611 |
| contradicted_claims | 2 |
| must_not_violations | 1 |
| refusal_ok | 2/2 |
| mean_studies_cited | 20.3 |
| mean_seconds | 43.7 |
| openrouter_spend_usd | 0.584 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.75 | 0 | 34 | 34/91 | None | 54.7 |
| grad-002 | synthesis | 0.667 | 0 | 39 | 38/91 | None | 47.1 |
| grad-003 | synthesis | 0.167 | 1 | 34 | 33/91 | None | 47.1 |
| grad-004 | synthesis | 0.667 | 0 | 29 | 27/91 | None | 43.2 |
| grad-005 | synthesis | 0.0 | 0 | 19 | 19/91 | None | 37.2 |
| grad-006 | synthesis | 1.0 | 0 | 36 | 35/91 | None | 40.8 |
| grad-007 | implementation | 0.3 | 0 | 28 | - | None | 39.0 |
| grad-008 | implementation | 0.667 | 0 | 25 | - | None | 40.7 |
| grad-009 | implementation | 0.625 | 0 | 27 | - | None | 39.8 |
| grad-010 | cost | 0.375 | 1 | 21 | - | None | 43.2 |
| grad-011 | cost | 0.438 | 0 | 17 | - | None | 43.2 |
| grad-012 | country | 0.5 | 0 | 1 | - | None | 37.5 |
| grad-013 | country | 0.583 | 0 | 3 | 1/1 | None | 40.6 |
| grad-014 | country | 0.167 | 0 | 2 | 1/1 | None | 44.3 |
| grad-015 | synthesis | 0.5 | 0 | 30 | 28/91 | None | 50.0 |
| grad-016 | gap | 1.0 | 0 | 4 | - | True | 45.9 |
| grad-017 | gap | 1.0 | 0 | 18 | - | True | 57.2 |
| grad-018 | gap | 0.438 | 0 | 19 | - | None | 43.4 |
| grad-019 | multilingual | 1.0 | 0 | 3 | 2/3 | None | 35.5 |
| grad-020 | synthesis | 0.5 | 0 | 17 | 16/91 | None | 43.9 |
