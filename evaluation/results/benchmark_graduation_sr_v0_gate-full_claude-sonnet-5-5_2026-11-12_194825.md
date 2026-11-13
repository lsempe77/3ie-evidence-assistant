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
| reading_spend_usd_shared | 0.5333 |
| judge_models | ['anthropic/claude-sonnet-5.5', 'openai/gpt-6-sol'] |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.566 |
| mean_claim_score_by_judge | {'anthropic/claude-sonnet-5.5': 0.615, 'openai/gpt-6-sol': 0.518} |
| mean_study_claim_score | 0.59 |
| contradicted_claims | 1 |
| must_not_violations | 0 |
| refusal_ok | 2/2 |
| mean_studies_cited | 21.9 |
| mean_seconds | 36.0 |
| openrouter_spend_usd | 0.7025 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.625 | 0 | 32 | 31/91 | None | 48.6 |
| grad-002 | synthesis | 0.667 | 0 | 32 | 32/91 | None | 44.7 |
| grad-003 | synthesis | 0.417 | 1 | 29 | 29/91 | None | 36.6 |
| grad-004 | synthesis | 0.667 | 0 | 26 | 26/91 | None | 33.4 |
| grad-005 | synthesis | 0.5 | 0 | 20 | 19/91 | None | 37.9 |
| grad-006 | synthesis | 0.75 | 0 | 35 | 34/91 | None | 34.8 |
| grad-007 | implementation | 0.45 | 0 | 26 | - | None | 39.1 |
| grad-008 | implementation | 0.333 | 0 | 34 | - | None | 34.3 |
| grad-009 | implementation | 0.375 | 0 | 24 | - | None | 35.6 |
| grad-010 | cost | 0.5 | 0 | 24 | - | None | 31.4 |
| grad-011 | cost | 0.25 | 0 | 21 | - | None | 31.1 |
| grad-012 | country | 0.5 | 0 | 9 | - | None | 32.4 |
| grad-013 | country | 0.5 | 0 | 14 | 1/1 | None | 41.0 |
| grad-014 | country | 0.25 | 0 | 4 | 1/1 | None | 28.9 |
| grad-015 | synthesis | 0.667 | 0 | 34 | 31/91 | None | 38.3 |
| grad-016 | gap | 1.0 | 0 | 3 | - | True | 41.9 |
| grad-017 | gap | 0.75 | 0 | 14 | - | True | 30.6 |
| grad-018 | gap | 0.625 | 0 | 20 | - | None | 30.6 |
| grad-019 | multilingual | 1.0 | 0 | 16 | 2/3 | None | 36.0 |
| grad-020 | synthesis | 0.5 | 0 | 20 | 19/91 | None | 32.2 |
