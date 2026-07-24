"""
app/services/ranking.py

Turns raw pairwise scores (from scoring.py) into an ordered list of
candidates for a given user. Kept separate from scoring.py so ranking
strategy (e.g. adding pagination, filtering by "already matched") can
change without touching the scoring math itself.
"""

from app.services.scoring import calculate_score


def rank_candidates(current_user, candidates):
    """
    Given a current user and a list of candidate User objects, returns
    them sorted by compatibility score, highest first.
    Each entry: {"user": <User>, "score": float}
    """
    scored = [
        {"user": candidate, "score": calculate_score(current_user, candidate)}
        for candidate in candidates
        if candidate.id != current_user.id
    ]
    return sorted(scored, key=lambda entry: entry["score"], reverse=True)


def find_best_matches(current_user, all_users, top_n=5):
    """Filters out the current user, ranks everyone else, returns top N
    as {"user": <User>, "score": float} dicts."""
    candidates = [u for u in all_users if u.id != current_user.id]
    ranked = rank_candidates(current_user, candidates)
    return ranked[:top_n]
