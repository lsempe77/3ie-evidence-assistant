"""Grounding of study facts (src/extraction/study_facts.py), no model calls."""

from src.extraction.study_facts import document_text, ground

DOC = """[p. 3]
Women comprised 88.8% of the participants.
The programme cost USD 1,250 per household in 2019 prices, of which the asset transfer was USD 540.
[p. 9]
The benefit-cost ratio is 133% after ten years.
Income rose by 12% relative to the control group 24 months after the start.
Poverty fell by 5.3 percentage points.
The probability of extreme poverty was reduced by 17.5%."""


def test_document_text_marks_pages_and_keeps_tables():
    cl = [{"type": "text", "text": "Intro", "page_idx": 1}, {"type": "table", "text": "| a | b |", "page_idx": 2},
          {"type": "image", "page_idx": 2}, {"type": "text", "text": "More", "page_idx": 2}]
    assert document_text(cl) == "\n[p. 1]\nIntro\n\n[p. 2]\n| a | b |\nMore"


def test_ground_keeps_quoted_figures_and_drops_the_rest():
    raw = {
        "is_impact_evaluation": True, "programme": "X, Peru", "countries": ["Peru"],
        "women_main_recipients": "yes", "women_quote": "Women comprised 88.8% of the participants.",
        "cost_per_beneficiary": [
            {"amount": "1,250", "currency": "USD", "price_year": "2019 prices", "unit": "per household",
             "quote": "The programme cost USD 1,250 per household in 2019 prices", "page": 3},
            {"amount": "999", "currency": "USD", "quote": "The programme cost USD 1,250 per household", "page": 3},
            {"amount": "700", "currency": "USD", "quote": "a quote that is not in the document at all", "page": 3},
        ],
        "transfer_value": [{"amount": "540", "currency": "USD", "quote": "the asset transfer was USD 540", "page": 3}],
        "benefit_cost": [{"ratio": "133%", "horizon_years": "10", "quote": "The benefit-cost ratio is 133% after ten years.", "page": 9}],
        "headline_effects": [
            {"outcome": "income", "direction": "increase", "percent_change": "12%", "months_after_start": "24",
             "significant": "yes", "quote": "Income rose by 12% relative to the control group", "page": 9},
            {"outcome": "poverty", "direction": "decrease", "percent_change": "5.3",
             "quote": "Poverty fell by 5.3 percentage points.", "page": 9},
            {"outcome": "poverty", "direction": "decrease", "percent_change": "17.5%",
             "quote": "The probability of extreme poverty was reduced by 17.5%.", "page": 9},
            {"outcome": "assets", "percent_change": "40", "quote": "Assets doubled, a quote not in the text", "page": 9},
        ],
        "followup_months": [24, "36", "x"],
    }
    f = ground(raw, DOC)
    assert f["women_main_recipients"] == "yes"
    assert [c["amount"] for c in f["cost_per_beneficiary"]] == [1250.0]  # wrong number and unquoted cost dropped
    assert f["cost_per_beneficiary"][0]["price_year"] == 2019
    assert f["transfer_value"][0]["amount"] == 540.0
    assert f["benefit_cost"][0]["ratio"] == 1.33 and f["benefit_cost"][0]["horizon_years"] == 10
    income, points, extreme = f["headline_effects"]
    assert income["percent_change"] == 12.0 and income["months_after_start"] == 24
    assert points["percent_change"] is None  # percentage points are not a relative change
    assert extreme["percent_change"] == -17.5  # decreases are negative
    assert f["followup_months"] == [24, 36]


def test_ground_drops_an_unsupported_women_flag():
    f = ground({"women_main_recipients": "yes", "women_quote": "Only women took part."}, DOC)
    assert f["women_main_recipients"] == "not_stated" and f["women_quote"] == ""
