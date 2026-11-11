"""Findings reported from other studies are never evidence (rule, 11 Nov 2026)."""

from src.extraction.secondhand import cites_other_study
from src.extraction.study_facts import ground


def test_author_year_citations_are_detected():
    assert cites_other_study("Banerjee et al. (2015), evaluating six graduation programs, find positive effects")
    assert cites_other_study("as found in Peru (Banerjee et al., 2015)")
    assert cites_other_study("Kidd and Bailey (2017) caution that impacts fade")
    assert cites_other_study("consistent with earlier work (Bandiera & Burgess, 2017b)")


def test_own_findings_are_not_flagged():
    assert not cites_other_study("Income rose by 12% relative to the control group 24 months after the start.")
    assert not cites_other_study("The programme ran from 2015 to 2018 in 40 villages.")
    assert not cites_other_study("In 2019, 88.8% of the participants were women.")


def test_study_facts_drop_figures_quoted_from_other_studies():
    doc = ("Our programme raised income by 12% relative to the control group. "
           "Banerjee et al. (2015) report a benefit-cost ratio of 133% in Ethiopia.")
    f = ground({"is_impact_evaluation": True,
                "benefit_cost": [{"ratio": "133%", "quote": "Banerjee et al. (2015) report a benefit-cost ratio of 133% in Ethiopia."}],
                "headline_effects": [{"outcome": "income", "direction": "increase", "percent_change": "12%",
                                      "quote": "Our programme raised income by 12% relative to the control group."}]}, doc)
    assert f["benefit_cost"] == []
    assert f["headline_effects"][0]["percent_change"] == 12.0
