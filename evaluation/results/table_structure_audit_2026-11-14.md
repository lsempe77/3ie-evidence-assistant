# Table-structure coverage audit

Tables parsed from 97 documents: 1617. Documents with at least one table: 93.
Tables with an estimate column or estimate row (results tables): 521 (32%). The rest are mostly descriptive tables (treatments, modules, sample sizes), which correctly have no estimate.

| Layout | Tables |
| --- | --- |
| statistics in columns | 1462 (90%) |
| statistics in rows | 155 (10%) |

## Table type (TVET phase 2 definitions)

| Type | Tables | Of those, an estimate was read |
| --- | --- | --- |
| results | 456 (28%) | 267 |
| descriptive | 210 (13%) | 81 |
| unknown | 951 (59%) | 173 |

## Coverage among results tables

| Structure found | Of the tables with an estimate |
| --- | --- |
| standard error (column or in the estimate cell) | 353 (68%) |
| p-value | 69 (13%) |
| confidence interval, both bounds | 4 (1%) |

| Structure found | All tables |
| --- | --- |
| estimate column | 521 (32%) |
| standard error column | 488 (30%) |
| combined estimate and SE in one cell | 210 (13%) |

Mean confidence: 0.67.
Mean share of columns left unknown, on results tables: 38%.

## Non-outcome rows in our extracted estimates

514 of 10014 rows carry a non-outcome label such as Observations, R2, Constant, Controls, SD or Clusters. Top labels: `Mean in Pure Control` 258; `Mean in control` 29; `Mean in Control group` 23; `Constant` 21; `Mean control` 18; `Mean for middle class` 16; `Mean for upper class` 16; `Mean for other poor` 12.

## Notes conventions

| Notes convention | Tables |
| --- | --- |
| notes state SE in parentheses | 687 (42%) |
| notes state a star map | 305 (19%) |
| notes mention a CI | 21 (1%) |

## Caption classifier against the estimate reader

Descriptive by caption, yet an estimate was read (check which side is wrong):
- caption `Table 5: Means of baseline characteristics for endline sample (standard deviations in pare` / header ` | Control | T1 (GrpLH/ GrpC) | T2 (IndLH/ GrpC) mean | T3 (IndLH/ IndC) | C v. T1 | C v. `
- caption `Appendix 3. Baseline (2002) value of the outcome variables of interest` / header `Outcome variable (mean) | Participants | Non-participants | Difference`
- caption `Table 3. Impact estimate of per capita income after controlling for baseline characteristi` / header `Explanatory variable | Coefficient`
- caption `Tabla 3.7 Probit-perfil de quienes no fueron entrevistados en la revisita (attrition)` / header `Variables explicativas | Coeficiente`
- caption `Table 1: Balance across key variables` / header ` | (1) - Obs. | (2) Control - Mean | (3) Full - Package | (4) Financial - Capital | (5) Hu`
- caption `Table B2: Intent-to-treat estimates: Attrition` / header ` | (1) - Obs. | (2) Control - Mean, [s.d.] | (3) Full - Package | (4) Financial - Capital `
- caption `Table B3: Impacts: Aggregate measures (w/ LASSO-selected covariates)` / header ` | (1) Obs. | (2) Control Mean, [s.d.] | (3) Full Package | (4) Financial Capital | (5) Hu`
- caption `Table 9: Indirect Effects on the Family Network of STUPs II` / header ` | (1) Pce | (2) Durables Value | (3) Radios | (4) Bicycles | (5) Chairs | (6) Tables | (7`
- caption `Table 1. Baseline characteristics of the participants and comparison groups` / header ` | Average for beneficiaries | Difference between participants and - Not-selected ultra-po`
- caption `Table 8. Impact estimates controlling for baseline variables` / header `VARIABLES | Impact compared to NSUP | Impact compared to comparison villages`

Results by caption, yet no estimate was read (a table the reader misses):
- caption `Table 3.4. Power calculations for the nutrition outcomes based on SPIR-I endline data, ori` / header ` | Original power calculations - Caregiver IYCF knowledge | Original power calculations - `
- caption `Table 10: Treatment effects on key welfare outcomes` / header ` | (1) Monthly consumption per capita (pesos) | (2) Food security index | (3) Value of pro`
- caption `Table 4: Average treatment effects by group-year on total value (in SSP) of all assets mea` / header ` | Total | Productive`
- caption `Table 5: Average treatment effects by group-year on percentage of households reporting any` / header `% > 0 | Savings | Food Sav | LandCult | LandOwn`
- caption `Table 6: Average treatment effects by group-year on total value (in SSP) of all cash and f` / header `Amt. | Savings | Food Sav | LandCult | LandOwn`
- caption `Table 7: Average treatment effects by group-year on total value (in SSP) of income reporte` / header ` | Farm | Livestock | Non-Farm | Total`
- caption `Table 8: Average treatment effects by group-year on the probability of having been affecte` / header ` | Affected | Migrated | NoInvest | NoMeans | ProtectLives | Worried`
- caption `Annex 10. Impact on safe water use and sanitation` / header ``
- caption `Table 1. Difference-in-difference (DD) and DD-PSM estimates of the impact of the TUP progr` / header ``
- caption `Table 3. Difference-in-difference (DD) and DD-PSM estimates of the impact of the TUP progr` / header `(no header)`

## Header words on likely results tables that were not read (top 20)

| Header row | Tables |
| --- | --- |
| `(no header)` | 30 |
| ` | (1) Depression severity score (PHQ-9, 0- 27) | (2) Depression severity score is 8 or hi` | 4 |
| ` | (1) Primary female has personal savings of her own | (2) Primary female's amount of sav` | 3 |
| ` | (1) Household has taken out a loan for productive purposes in the last 12 months | (2) ` | 3 |
| ` | (1) Female has taken out a loan for productive purposes in the last 12 months | (2) Fem` | 3 |
| ` | (1) Household owns at least one sickle | (2) Household owns at least one axe | (3) Hous` | 3 |
| ` | (1) Total value of food consumption per month per adult equivalent (birr) | (2) Monthly` | 3 |
| ` | (1) Respects his spouse most of the time* | (2) Feels his spouse respects him most of t` | 3 |
| ` | (1) Locus of control (1-10) | (2) Input into most decisions about how much inputs to be` | 3 |
| `Sub-Purpose | Key Findings from the Qualitative and Quantitative Research` | 3 |
| `Variables | EI1 - Effect | EI1 - Effect SD of GC | EI2 - Effect | EI2 - SD of GC Effect | ` | 3 |
| `Panel A: Followup survey 1 | Total quantity of production (IHST) of … - Maize (1) | Total ` | 3 |
| ` | (1) | (2) | (3) | (4) | (5) | (6)` | 3 |
| `Variables | IV - Effect | IV - SD of CG | RE - Change | RE - SD of BL` | 3 |
| `Number of - indicators satisfied | 2002 - SUP | 2002 - NSUP | 2005 - SUP | 2005 - NSUP | 2` | 2 |
| ` | (1) Female savings | (2) Female credit | (3) Male savings | (4) Male credit | (5) Aggre` | 2 |
| ` | (1) Woman reports owning any poultry (solely or jointly owned) | (2) Man reports househ` | 2 |
| ` | (1) Net income from sales of livestock products (eggs, milk, dairy, honey) in past 12 m` | 2 |
| ` | (1) Household has any savings (with RUSACCO, VESA, VSLA, MFI, bank, at home, with a rel` | 2 |
| ` | (1) Women's dietary diversity score (1- 10) | (2) Met minimum dietary diversity for wom` | 2 |