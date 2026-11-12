"""Quote verification: the reader's quote must be real text from the passages."""

from src.extraction.quotes import verify_quote

PASSAGES = (
    "We also find that the treated individuals in rural areas gain significant income from "
    "business, livestock farming, and agriculture by switching employment.\n\n"
    "Household consumption rose by 0.17 standard deviations relative to the control group."
)


def test_exact_quote_is_kept():
    quote = "Household consumption rose by 0.17 standard deviations relative to the control group."
    assert verify_quote(quote, PASSAGES) == quote


def test_whitespace_and_case_differences_are_tolerated():
    quote = "household   consumption ROSE by 0.17 standard deviations"
    assert verify_quote(quote, PASSAGES).lower().startswith("household consumption rose")


def test_a_reflowed_quote_snaps_to_its_source_sentence():
    quote = "the treated individuals in rural areas gain significant income from business farming"
    snapped = verify_quote(quote, PASSAGES)
    assert snapped.startswith("We also find that the treated individuals in rural areas")


def test_a_fabricated_quote_is_dropped():
    assert verify_quote("The programme halved poverty in every region studied.", PASSAGES) == ""


def test_a_quote_too_short_to_highlight_is_dropped():
    assert verify_quote("consumption rose", PASSAGES) == ""
