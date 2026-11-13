# Normalisation audit (P0)

Rows in our per-study extraction: 10014 across 86 studies. Human key rows: 443 across 43 studies.

## Parsable but unparsed

| Variant in the printed cell | Rows with it | Of those, field not parsed |
| --- | --- | --- |
| paren SE in cell | 2126 | 0 |
| CI bracket pair | 7 | 0 |
| stars | 2748 | 0 |
| p in cell | 0 | 0 |
| p given in p_value_text | 3196 | 8 |

Examples of unparsed cells:

## Agreement with the human key

Joinable studies (numeric id): 41. Human rows in them: 433. Our rows in them: 4335. Rows matched on outcome and arm: 64.

| Field | Compared | Equal |
| --- | --- | --- |
| estimate | 64 | 12 |
| se | 52 | 10 |
| p | 41 | 2 |
| n_total | 23 | 6 |

Label-free value recall (does our extraction for the study contain the human value at all):
estimate 168 of 433, SE 154 of 406.

## TVET hand-check formats

Second corpus, for the variant taxonomy: paren SE in cell 478, stars 208, CI bracket pair 8.
