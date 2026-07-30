"""
app/services/recommendation_engine.py

Public-facing facade for the recommendation system. Routes (Person B's
match_routes.py) should import from HERE rather than reaching into
scoring.py/ranking.py directly -- this file is the stable interface;
the internals underneath it can be refactored freely.

Exposes:
    calculate_score(user1, user2)      -> float
    rank_candidates(user, candidates)  -> list[{"user", "score"}]
    find_best_matches(user, all_users) -> list[{"user", "score", "reasons"}]
    explain_match(user1, user2)        -> {"score": float, "reasons": [str]}
"""

from app.services.scoring import calculate_score, _expand_slots, overlapping_windows
from app.services.ranking import rank_candidates, find_best_matches as _find_best_matches


def explain_match(user1, user2):
    """
    Returns the score plus human-readable reasons, e.g.:
    {
        "score": 92.0,
        "reasons": ["3 overlapping study time block(s)", "Shared course(s): CS101", ...],
        "overlapping_availability": [{"day": "monday", "start": "14:00", "end": "16:00"}, ...]
    }
    """
    score = calculate_score(user1, user2)
    reasons = []

    overlap_slots = _expand_slots(user1.availability_slots) & _expand_slots(user2.availability_slots)
    if overlap_slots:
        reasons.append(f"{len(overlap_slots)} overlapping study time block(s)")
    else:
        reasons.append("No overlapping availability")

    shared_courses = {c.name for c in user1.courses} & {c.name for c in user2.courses}
    if shared_courses:
        reasons.append(f"Shared course(s): {', '.join(sorted(shared_courses))}")

    if user1.preference and user2.preference:
        if user1.preference.study_style == user2.preference.study_style:
            reasons.append(f"Same study style ({user1.preference.study_style})")
        if abs(user1.preference.pace - user2.preference.pace) <= 1:
            reasons.append("Similar study pace")

    return {
        "score": score,
        "reasons": reasons,
        "overlapping_availability": overlapping_windows(user1, user2),
    }


def find_best_matches(current_user, all_users, top_n=5):
    """Same ranking as ranking.find_best_matches, but each result includes
    explainable reasons -- this is what routes should call for the
    'top matches' endpoint."""
    top = _find_best_matches(current_user, all_users, top_n=top_n)
    return [
        {
            "user": entry["user"].to_dict(),
            **explain_match(current_user, entry["user"]),
        }
        for entry in top
    ]


__all__ = ["calculate_score", "rank_candidates", "find_best_matches", "explain_match"]
