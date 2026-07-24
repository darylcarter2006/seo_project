"""
Compatibility scoring between two students for the study-group matcher.

Superseded by app/services/recommendation_engine.py, which is what
match_routes.py now calls -- it works against the real User/Availability
DB schema instead of raw dicts. Kept here (unused by routes) since its
own tests still exercise it standalone; not deleted in this pass.

Expected input shape for each student's availability:
    {
        "monday":    [("14:00", "16:00"), ("18:00", "20:00")],
        "tuesday":   [("10:00", "12:00")],
        ...
    }
Times are 24-hour "HH:MM" strings.
"""

from datetime import datetime


def _time_to_minutes(time_str):
    """Convert 'HH:MM' into minutes since midnight, so ranges are easy to compare."""
    t = datetime.strptime(time_str, "%H:%M")
    return t.hour * 60 + t.minute


def _overlap_minutes(block_a, block_b):
    """Given two (start, end) time blocks, return how many minutes overlap."""
    start_a, end_a = _time_to_minutes(block_a[0]), _time_to_minutes(block_a[1])
    start_b, end_b = _time_to_minutes(block_b[0]), _time_to_minutes(block_b[1])

    latest_start = max(start_a, start_b)
    earliest_end = min(end_a, end_b)

    return max(0, earliest_end - latest_start)


def calculate_availability_overlap(availability_a, availability_b):
    """
    Sums total overlapping minutes across all shared days between two
    students' availability dicts.

    Returns:
        int: total overlapping minutes across the whole week
    """
    total_overlap = 0

    for day, blocks_a in availability_a.items():
        blocks_b = availability_b.get(day, [])
        for block_a in blocks_a:
            for block_b in blocks_b:
                total_overlap += _overlap_minutes(block_a, block_b)

    return total_overlap


def calculate_compatibility_score(student_a, student_b):
    """
    Combines course match + availability overlap into a single score.

    student_a / student_b are expected to be dicts like:
        {"course_id": 101, "availability": {...}}

    Returns:
        float: a score from 0.0 to 1.0, higher = better match
    """
    if student_a["course_id"] != student_b["course_id"]:
        return 0.0  # not in the same class, no match at all

    overlap_minutes = calculate_availability_overlap(
        student_a["availability"], student_b["availability"]
    )

    # Cap at 300 minutes (5 hours) of overlap for a perfect score.
    # Anything beyond that doesn't make them "more compatible."
    MAX_USEFUL_OVERLAP = 300
    availability_score = min(overlap_minutes / MAX_USEFUL_OVERLAP, 1.0)

    return availability_score


def find_best_matches(target_student, candidate_students, top_n=5):
    """
    Given one student and a list of candidates, returns the top N matches
    ranked by compatibility score.

    Returns:
        list of tuples: [(candidate_dict, score), ...] sorted highest first
    """
    scored = [
        (candidate, calculate_compatibility_score(target_student, candidate))
        for candidate in candidate_students
    ]

    scored = [pair for pair in scored if pair[1] > 0]  # drop zero-score matches
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return scored[:top_n]