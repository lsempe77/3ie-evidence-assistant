"""
Table-type and non-outcome rules, ported from the TVET pipeline.

Two problems make a results table hard to read, and both were already solved once in TVET
(`pipelines/TVET/pipeline/`, outside this repo):

1. Telling a results table from a descriptive one. A balance table, a summary of baseline
   characteristics or an attrition table looks like a results table: it has rows and numbers. But
   its numbers are means, differences or balance-test statistics, not treatment effects. TVET's
   `prompts/phase2_table_filtering.txt` names the distinction, and `validation_rules.py` flags
   balance, matching and propensity tables.
2. Rows and columns that are not outcomes. "Observations", "R²", "Constant", a list of controls, or
   a column of means and standard deviations sit inside real results tables but are not estimates.
   TVET's `validation_rules.py` (`observations_check`, `goodness_of_fit_check`, `controls_check`,
   `covariate_check`, `column_label_check`) excludes them by pattern.

This module ports those ideas as pure functions: no model, no config file, no I/O. Patterns are
listed here so they are visible and testable. Provenance: TVET phase 2 and `validation_rules.yaml`.
"""

from __future__ import annotations

import re
import unicodedata

RESULTS = "results"
DESCRIPTIVE = "descriptive"
UNKNOWN = "unknown"

# Caption, section and note cues. A descriptive cue wins, because a balance table named
# "Baseline characteristics and impacts" is still a balance table.
_DESCRIPTIVE_CUES = (
    "balance", "baseline", "baseline characteristics", "summary statistics", "descriptive",
    "demographics", "sample characteristics", "attrition", "covariate", "covariates",
    "pre-treatment", "pretreatment", "randomization check", "randomisation check", "first stage",
    "falsification", "placebo", "take-up only", "compliance rates", "summary of sample",
)
_RESULTS_CUES = (
    "impact", "effect", "treatment effect", "effects of", "regression", "coefficient", "estimates",
    "estimation results", "main results", "itt", "att", "ate", "difference-in-difference",
    "double difference", "differences-in-differences", "results",
)
# Row labels that appear in results tables but are not outcomes.
_NON_OUTCOME = (
    "observations", "number of observations", "n obs", "nobs", "r-squared", "r squared", "r2",
    "adjusted r", "constant", "intercept", "controls", "control variables", "covariates",
    "fixed effects", "f-statistic", "f stat", "p-value", "p value", "standard deviation",
    "mean", "average", "clusters", "number of clusters",
)
_NON_OUTCOME_EXACT = {"n", "obs", "sd", "se", "r2", "r²"}


def _fold(text: object) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(text or "")) if not unicodedata.combining(c))


def _norm(text: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _fold(text).lower()).strip()


def classify_table(caption: str = "", notes: str = "", header: str = "") -> tuple[str, str]:
    """`results`, `descriptive` or `unknown`, with the cue that decided it."""
    text = _norm(f"{caption} {notes} {header}")
    if not text:
        return UNKNOWN, "no caption, notes or header"
    for cue in _DESCRIPTIVE_CUES:
        if re.search(rf"\b{re.escape(cue)}(?:s|es)?\b", text):
            return DESCRIPTIVE, f"descriptive cue '{cue}'"
    for cue in _RESULTS_CUES:
        if re.search(rf"\b{re.escape(cue)}(?:s|es)?\b", text):
            return RESULTS, f"results cue '{cue}'"
    return UNKNOWN, "no cue"


def is_non_outcome_label(label: str) -> bool:
    """True for a row label that sits in a results table but is not an outcome."""
    key = _norm(label)
    if not key:
        return False
    if key in _NON_OUTCOME_EXACT:
        return True
    # "Average effect of T1" is an effect, not a control mean; "Mean in pure control" is a mean.
    if re.search(r"\b(mean|average|avg)\b.*\b(effect|impact)\b", key):
        return False
    # "Prob > F" is a p-value; "probability of employment" is an outcome, so prob is matched exactly.
    if key == "prob" or key.startswith("prob ") or "prob >" in key:
        return True
    return any(cue in key for cue in _NON_OUTCOME)


def is_descriptive_column(header: str) -> bool:
    """True for a column of means or standard deviations, which are not estimates."""
    key = _norm(header)
    return bool(re.search(r"\b(mean|average|sd|std dev|standard deviation)\b", key))
