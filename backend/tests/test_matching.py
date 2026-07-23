import unittest
from app.services.matching_service import (
    calculate_availability_overlap,
    calculate_compatibility_score,
    find_best_matches,
)


class TestAvailabilityOverlap(unittest.TestCase):

    def test_full_overlap(self):
        a = {"monday": [("14:00", "16:00")]}
        b = {"monday": [("14:00", "16:00")]}
        self.assertEqual(calculate_availability_overlap(a, b), 120)

    def test_partial_overlap(self):
        a = {"monday": [("14:00", "16:00")]}
        b = {"monday": [("15:00", "17:00")]}
        self.assertEqual(calculate_availability_overlap(a, b), 60)

    def test_no_overlap_same_day(self):
        a = {"monday": [("09:00", "10:00")]}
        b = {"monday": [("14:00", "16:00")]}
        self.assertEqual(calculate_availability_overlap(a, b), 0)

    def test_no_overlap_different_days(self):
        a = {"monday": [("14:00", "16:00")]}
        b = {"tuesday": [("14:00", "16:00")]}
        self.assertEqual(calculate_availability_overlap(a, b), 0)

    def test_empty_availability(self):
        a = {}
        b = {"monday": [("14:00", "16:00")]}
        self.assertEqual(calculate_availability_overlap(a, b), 0)


class TestCompatibilityScore(unittest.TestCase):

    def test_different_courses_returns_zero(self):
        alice = {"course_id": 101, "availability": {"monday": [("14:00", "16:00")]}}
        dan = {"course_id": 202, "availability": {"monday": [("14:00", "16:00")]}}
        self.assertEqual(calculate_compatibility_score(alice, dan), 0.0)

    def test_same_course_full_overlap_scores_near_one(self):
        alice = {"course_id": 101, "availability": {"monday": [("14:00", "19:00")]}}
        bob = {"course_id": 101, "availability": {"monday": [("14:00", "19:00")]}}
        self.assertEqual(calculate_compatibility_score(alice, bob), 1.0)


if __name__ == "__main__":
    unittest.main()
