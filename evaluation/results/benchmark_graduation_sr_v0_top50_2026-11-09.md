# Benchmark graduation_sr_v0.yaml: top50, RETRIEVAL_TOP_K=50 from local .env (2026-11-09)

| Metric | Value |
| --- | --- |
| benchmark | graduation_sr_v0.yaml |
| label | top50 |
| date | 2026-11-09 |
| project_id | 7efdc60e-e863-480c-929e-616574725e5f |
| judge_model | anthropic/claude-sonnet-5.5 |
| items | 20 |
| errors | 0 |
| mean_claim_score | 0.283 |
| contradicted_claims | 1 |
| must_not_violations | 2 |
| refusal_ok | 0/2 |
| mean_studies_cited | 7.2 |
| mean_seconds | 44.7 |
| openrouter_spend_usd | 0.2073 |

| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| grad-001 | synthesis | 0.0 | 0 | 0 | 0/91 | None | 44.1 |
| grad-002 | synthesis | 0.333 | 0 | 10 | 10/91 | None | 48.1 |
| grad-003 | synthesis | 0.167 | 0 | 10 | 8/91 | None | 42.7 |
| grad-004 | synthesis | 0.5 | 0 | 10 | 10/91 | None | 50.2 |
| grad-005 | synthesis | 0.0 | 0 | 0 | 0/91 | None | 16.1 |
| grad-006 | synthesis | 0.5 | 0 | 10 | 9/91 | None | 40.8 |
| grad-007 | implementation | 0.2 | 0 | 10 | - | None | 45.8 |
| grad-008 | implementation | 0.167 | 0 | 8 | - | None | 40.2 |
| grad-009 | implementation | 0.25 | 0 | 5 | - | None | 40.4 |
| grad-010 | cost | 0.25 | 0 | 9 | - | None | 38.9 |
| grad-011 | cost | 0.25 | 0 | 10 | - | None | 51.2 |
| grad-012 | country | 0.25 | 0 | 3 | - | None | 34.4 |
| grad-013 | country | 0.167 | 0 | 2 | 1/1 | None | 41.4 |
| grad-014 | country | 0.167 | 0 | 5 | 1/1 | None | 53.7 |
| grad-015 | synthesis | 0.333 | 0 | 10 | 7/91 | None | 50.7 |
| grad-016 | gap | 1.0 | 0 | 9 | - | False | 53.4 |
| grad-017 | gap | 0.0 | 0 | 10 | - | False | 53.7 |
| grad-018 | gap | 0.125 | 0 | 10 | - | None | 51.9 |
| grad-019 | multilingual | 0.5 | 1 | 2 | 2/3 | None | 46.2 |
| grad-020 | synthesis | 0.5 | 0 | 10 | 9/91 | None | 50.5 |
