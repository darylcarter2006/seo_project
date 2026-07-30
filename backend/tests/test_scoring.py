"""
tests/test_scoring.py
Priority 2/4 verification: the pure scoring math in app/services/scoring.py.
"""

import pytest
from app.services.persistence import get_or_create_course
from app.services.scoring import calculate_score, overlapping_windows
from tests.conftest import make_user


def test_identical_availability_and_style_scores_highly(app):
    course = get_or_create_course("CS101", "Intro to CS")
    u1 = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3, course)
    u2 = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3, course)
    assert calculate_score(u1, u2) > 90


def test_no_shared_availability_scores_low(app):
    u1 = make_user("Ava", "ava@example.edu", [(0, 8, 9)], "quiet", 1)
    u2 = make_user("Ben", "ben@example.edu", [(4, 20, 21)], "flashcards", 5)
    assert calculate_score(u1, u2) < 20


def test_score_is_symmetric(app):
    u1 = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    u2 = make_user("Ben", "ben@example.edu", [(0, 15, 17)], "discussion", 4)
    assert calculate_score(u1, u2) == calculate_score(u2, u1)


def test_cannot_score_user_against_self(app):
    u1 = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    with pytest.raises(ValueError):
        calculate_score(u1, u1)


def test_score_is_bounded_0_to_100(app):
    u1 = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    u2 = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3)
    score = calculate_score(u1, u2)
    assert 0 <= score <= 100


def test_user_with_no_availability_scores_zero_on_that_factor(app):
    u1 = make_user("Ava", "ava@example.edu", [], "quiet", 3)
    u2 = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3)
    # Should not crash on empty availability, and should score lower than
    # two users who both have overlapping slots.
    score = calculate_score(u1, u2)
    assert score < 50


def test_overlapping_windows_returns_exact_overlap_for_partial_block(app):
    u1 = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)  # Mon 14-16
    u2 = make_user("Ben", "ben@example.edu", [(0, 15, 18)], "quiet", 3)  # Mon 15-18
    assert overlapping_windows(u1, u2) == [{"day": "monday", "start": "15:00", "end": "16:00"}]


def test_overlapping_windows_merges_contiguous_hours_into_one_block(app):
    # Two separate Availability rows that are adjacent (14-15, 15-16) should
    # merge into a single 14:00-16:00 window, not two 1-hour windows.
    u1 = make_user("Ava", "ava@example.edu", [(0, 14, 15), (0, 15, 16)], "quiet", 3)
    u2 = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3)
    assert overlapping_windows(u1, u2) == [{"day": "monday", "start": "14:00", "end": "16:00"}]


def test_overlapping_windows_across_multiple_days_sorted_by_day(app):
    u1 = make_user("Ava", "ava@example.edu", [(2, 14, 16), (0, 9, 10)], "quiet", 3)  # Wed, Mon
    u2 = make_user("Ben", "ben@example.edu", [(0, 9, 10), (2, 14, 16)], "quiet", 3)
    assert overlapping_windows(u1, u2) == [
        {"day": "monday", "start": "09:00", "end": "10:00"},
        {"day": "wednesday", "start": "14:00", "end": "16:00"},
    ]


def test_overlapping_windows_empty_when_no_overlap(app):
    u1 = make_user("Ava", "ava@example.edu", [(0, 9, 10)], "quiet", 3)
    u2 = make_user("Ben", "ben@example.edu", [(1, 9, 10)], "quiet", 3)
    assert overlapping_windows(u1, u2) == []
