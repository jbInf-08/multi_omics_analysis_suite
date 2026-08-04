"""Applying homopolymer corrections must resize the run in both directions.

``_apply_corrections`` used to branch on ``true_length > current_length`` and
run the *same* statement in each arm, under comments saying "Insert bases" and
"Remove bases". That reads like a bug -- one arm looking as though it had been
pasted over the other -- but it is not: a list slice takes the length of
whatever replaces it, so a single assignment already grows and shrinks.

The branch is gone. These tests pin the behaviour it was obscuring, so the
collapse is backed by something that fails if the resizing ever stops working.
"""

from __future__ import annotations

import pytest

from backend.assembly.polishing import HomopolymerCorrector


@pytest.fixture
def corrector():
    return HomopolymerCorrector()


def test_run_is_extended_when_reads_support_a_longer_one(corrector):
    """3 observed T's, 5 estimated -> the sequence grows by two."""
    sequence = "ACGTTTACGT"
    result = corrector._apply_corrections(sequence, [(3, 6, "T", 5)])
    assert result == "ACGTTTTTACGT"
    assert len(result) == len(sequence) + 2


def test_run_is_shortened_when_reads_support_a_shorter_one(corrector):
    """3 observed T's, 1 estimated -> the sequence shrinks by two."""
    sequence = "ACGTTTACGT"
    result = corrector._apply_corrections(sequence, [(3, 6, "T", 1)])
    assert result == "ACGTACGT"
    assert len(result) == len(sequence) - 2


def test_run_is_unchanged_when_the_estimate_matches(corrector):
    sequence = "ACGTTTACGT"
    assert corrector._apply_corrections(sequence, [(3, 6, "T", 3)]) == sequence


def test_a_run_can_be_removed_entirely(corrector):
    """true_length of 0 deletes the run rather than leaving an empty marker."""
    assert corrector._apply_corrections("ACGTTTACGT", [(3, 6, "T", 0)]) == "ACGACGT"


def test_multiple_corrections_do_not_disturb_each_others_offsets(corrector):
    """Corrections are applied back-to-front, so earlier indices stay valid.

    Both runs change length here; if the ordering were wrong the second edit
    would land at a shifted position and corrupt the sequence.
    """
    sequence = "AAACGTTTGCA"
    result = corrector._apply_corrections(
        sequence,
        [(0, 3, "A", 5), (5, 8, "T", 1)],
    )
    assert result == "AAAAACGTGCA"


def test_corrections_are_sorted_regardless_of_input_order(corrector):
    """The method sorts internally, so caller order must not matter."""
    sequence = "AAACGTTTGCA"
    forward = corrector._apply_corrections(sequence, [(0, 3, "A", 5), (5, 8, "T", 1)])
    reverse = corrector._apply_corrections(sequence, [(5, 8, "T", 1), (0, 3, "A", 5)])
    assert forward == reverse


def test_no_corrections_returns_the_sequence_unchanged(corrector):
    assert corrector._apply_corrections("ACGTACGT", []) == "ACGTACGT"
