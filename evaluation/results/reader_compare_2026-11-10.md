# Reader comparison (2026-11-10), reference anthropic/claude-haiku-5.5, 20 questions

| Model | relevant | agreement_with_reference | kappa_with_reference | recall_of_reference_relevant | precision_vs_reference | direction_agreement | json_or_call_errors | numbers_found_in_passages | seconds_per_question | spend_per_question_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anthropic/claude-haiku-5.5 | 402 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 11 | 0.933 | 8.3 | 0.0111 |
| z-ai/glm-5.3-flash | 415 | 0.851 | 0.7 | 0.856 | 0.829 | 0.785 | 0 | 0.945 | 10.5 | 0.0088 |
| deepseek/deepseek-v4.1-flash-1017 | 359 | 0.876 | 0.749 | 0.813 | 0.911 | 0.817 | 21 | 0.923 | 20.3 | 0.007 |
| minimax/minimax-m3.1-flash | 372 | 0.863 | 0.724 | 0.816 | 0.882 | 0.768 | 1 | 0.937 | 9.3 | 0.005 |
