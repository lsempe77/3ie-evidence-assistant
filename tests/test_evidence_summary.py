"""Figures computed across a collection from study facts (src/agents/evidence_summary.py)."""

from src.agents.evidence_summary import programme_key, summary_lines


def facts(programme, women="not_stated", cost=None, transfer=None, ratio=None, income=None, countries=("Peru",)):
    return {
        "is_impact_evaluation": True, "programme": programme, "countries": list(countries),
        "women_main_recipients": women,
        "cost_per_beneficiary": [{"amount": cost, "currency": "USD"}] if cost else [],
        "transfer_value": [{"amount": transfer, "currency": "USD"}] if transfer else [],
        "benefit_cost": [{"ratio": ratio, "horizon_years": 10}] if ratio else [],
        "headline_effects": [{"outcome": "income", "percent_change": income}] if income is not None else [],
    }


COLLECTION = {
    "a1": facts("BRAC TUP, Bangladesh", women="yes", cost=300, transfer=150, ratio=3.79, income=10, countries=["Bangladesh"]),
    "a2": facts("BRAC TUP (CFPR), Bangladesh", women="yes", cost=500, income=20, countries=["Bangladesh"]),
    "b": facts("Haku Wiñay, Peru", women="no", cost=900, transfer=300, income=30),
    "c": facts("SPIR, Ethiopia", women="yes", cost=1500, income=5, countries=["Ethiopia"]),
    "d": facts("Programme D, Ghana", women="mixed", income=40, countries=["Ghana"]),
    "e": {**facts("Review", countries=[]), "is_impact_evaluation": False},
}


def test_programme_key_merges_name_variants_of_one_programme():
    assert programme_key(COLLECTION["a1"], "a1") == programme_key(COLLECTION["a2"], "a2") == "brac tup"
    assert programme_key({"programme": ""}, "x") == "doc:x"


def test_summary_counts_programmes_not_documents():
    lines = summary_lines(COLLECTION, {"a1": 3, "c": 7})
    text = "\n".join(lines)
    assert "5 impact evaluations of about 4 distinct programmes in 4 countries" in text
    assert "Women as the main recipients: 2 of the 4 programmes" in text
    # BRAC's two costs (300, 500) count once, as their median 400: programmes 400, 900, 1500
    assert "by 3 programmes" in text and "median 900, range 400 to 1,500" in text
    assert "BRAC TUP, Bangladesh 400 [3]" in text and "SPIR, Ethiopia 1,500 [7]" in text
    # Transfer shares: BRAC 150/400 = 38%, Haku Wiñay 300/900 = 33%
    assert "share of total cost, where both are reported (2 programmes): median 35%" in text
    assert "Benefit-cost ratios reported by 1 programme: median 3.79" in text


def test_income_gains_are_grouped_by_women_as_main_recipients():
    text = "\n".join(summary_lines(COLLECTION))
    # Women first: BRAC (median of 10, 20 = 15) and SPIR 5 -> median 10. Others: Haku Wiñay 30, D 40 -> 35
    assert "women as main recipients: median +10% across 2 programmes" in text
    assert "other programmes: median +35% across 2 programmes" in text


def test_no_facts_gives_no_lines():
    assert summary_lines({}) == []
