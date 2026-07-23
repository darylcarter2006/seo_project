"""
app/services/scoring.py

Pure compatibility-scoring math. No database writes happen here -- these
functions take User objects (with their relationships already loaded)
and return numbers. Keeping this pure makes it trivial to unit test
without touching the database.

Weights live in one place (WEIGHTS) so they're easy to tune/justify with
survey data instead of being scattered through the code.

Each sub-score is normalized to 0.0-1.0 BEFORE weighting, so no single
factor can dominate just because its raw numbers happen to be bigger
than another factor's.

calculate_score() is symmetric: calculate_score(a, b) == calculate_score(b, a).
This is tested explicitly in tests/test_scoring.py -- an asymmetric score
would be a real bug in a "compatibility" score.
"""

WEIGHTS = {
    "availability": 0.45,
    "course_overlap": 0.25,
    "study_style": 0.20,
    "pace": 0.10,
}


def _expand_slots(availability_slots):
    """Turn Availability rows into a set of (day, hour) tuples for overlap math."""
    expanded = set()
    for slot in availability_slots:
        for hour in range(slot.start_hour, slot.end_hour):
            expanded.add((slot.day_of_week, hour))
    return expanded


def availability_overlap_score(user1, user2):
    """Jaccard similarity of availability slots: overlap / union."""
    slots1 = _expand_slots(user1.availability_slots)
    slots2 = _expand_slots(user2.availability_slots)

    if not slots1 or not slots2:
        return 0.0

    union = slots1 | slots2
    if not union:
        return 0.0

    return len(slots1 & slots2) / len(union)


def course_overlap_score(user1, user2):
    """Jaccard similarity of course sets. Zero shared courses scores 0."""
    courses1 = {c.id for c in user1.courses}
    courses2 = {c.id for c in user2.courses}

    if not courses1 or not courses2:
        return 0.0

    union = courses1 | courses2
    if not union:
        return 0.0

    return len(courses1 & courses2) / len(union)


def study_style_score(user1, user2):
    """Exact match = 1.0, otherwise 0.0. Simple on purpose -- can be
    upgraded to a similarity table later without touching calculate_score."""
    p1, p2 = user1.preference, user2.preference
    if not p1 or not p2:
        return 0.0
    return 1.0 if p1.study_style == p2.study_style else 0.0


def pace_score(user1, user2):
    """Pace is 1-5. Score decays linearly with distance; max distance is 4."""
    p1, p2 = user1.preference, user2.preference
    if not p1 or not p2:
        return 0.0
    distance = abs(p1.pace - p2.pace)
    return max(0.0, 1.0 - (distance / 4))


def calculate_score(user1, user2):
    """Returns a compatibility score from 0-100 between two users."""
    if user1.id == user2.id:
        raise ValueError("Cannot score a user against themselves")

    sub_scores = {
        "availability": availability_overlap_score(user1, user2),
        "course_overlap": course_overlap_score(user1, user2),
        "study_style": study_style_score(user1, user2),
        "pace": pace_score(user1, user2),
    }

    weighted_total = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(weighted_total * 100, 1)
