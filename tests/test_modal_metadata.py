"""
Metadata resolution guards: a looked-up record is accepted only if its title is on the
paper's first pages, and the study design classifier sees the method passages.

The rejected titles below are real mismatches from the poverty graduation collection
(November 2026).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infrastructure"))
metadata = pytest.importorskip("modal_lib.metadata")

TUP_FIRST_PAGE = """
Long-Term Effects of the Targeting the Ultra Poor Program
Abhijit Banerjee, Esther Duflo, Garima Sharma
Abstract. This paper studies the long-term effects of a graduation programme in West Bengal,
India, which gave ultra-poor households a productive asset and training. See also
https://doi.org/10.1126/science.1260799 for the six-country evaluation.
"""


class TestTitleMatch:
    def test_own_title_is_accepted(self):
        assert metadata.title_matches_document(
            "Long-Term Effects of the Targeting the Ultra Poor Program", TUP_FIRST_PAGE)

    @pytest.mark.parametrize("wrong_title", [
        "Interpretation and machine translation towards google translate as a part of translation teaching",
        "Improving School Accountability Measures",
        "Post-secondary participation and graduation",
    ])
    def test_unrelated_records_are_rejected(self, wrong_title):
        assert not metadata.title_matches_document(wrong_title, TUP_FIRST_PAGE)

    def test_too_short_to_judge_is_rejected(self):
        assert not metadata.title_matches_document("Graduation", TUP_FIRST_PAGE)


class TestTitlesAgree:
    OWN = "Unbundling the impacts of economic empowerment programmes: evidence from a randomised trial in Malawi"

    def test_same_title_with_or_without_subtitle(self):
        assert metadata.titles_agree(self.OWN, self.OWN)
        assert metadata.titles_agree("Unbundling the Impacts of Economic Empowerment Programmes", self.OWN)

    @pytest.mark.parametrize("generic", [
        "How to Make Your Research & Publications Visible",
        "Journal of Development Economics",
        "Evidence",
    ])
    def test_generic_hits_are_rejected(self, generic):
        assert not metadata.titles_agree(generic, self.OWN)


class TestDoiCandidates:
    def test_all_dois_in_order_without_duplicates_or_trailing_punctuation(self):
        text = "doi:10.1016/j.worlddev.2012.05.021. Also 10.1126/science.1260799) and 10.1016/j.worlddev.2012.05.021"
        assert metadata.extract_dois_from_text(text) == [
            "10.1016/j.worlddev.2012.05.021", "10.1126/science.1260799"]


class TestDesignExcerpt:
    def test_method_paragraphs_follow_a_cover_page(self):
        cover = "UNITED NATIONS DEVELOPMENT REPORT\n\nContents\n\n" + ("Chapter list. " * 200)
        method = "We randomly assigned 120 villages to a treatment group and a control group at baseline."
        filler = "\n\n".join("General discussion of poverty policy." for _ in range(20))
        excerpt = metadata.build_design_excerpt(cover + "\n\n" + filler + "\n\n" + method)
        assert method in excerpt
        assert excerpt.startswith("UNITED NATIONS")

    def test_abstract_leads_when_given(self):
        assert metadata.build_design_excerpt("x" * 100, abstract="An RCT in Ghana.").startswith("An RCT in Ghana.")
