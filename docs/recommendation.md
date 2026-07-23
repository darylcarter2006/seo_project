# Recommendation Engine

## Overview

Compatibility between two students is a weighted combination of four
factors, each normalized to 0.0–1.0 before weighting so no single factor
dominates just because its raw numbers happen to be larger.

## Weights

Defined in `app/services/scoring.py`:

| Factor | Weight | Rationale |
|---|---|---|
| Availability overlap | 0.45 | Highest weight — our survey found scheduling conflicts are the most commonly cited reason study groups fail |
| Course overlap | 0.25 | Shared coursework is the primary practical reason to study together |
| Study style match | 0.20 | Compatibility in how people prefer to study (quiet/discussion/flashcards) |
| Pace match | 0.10 | Lowest weight — a secondary comfort factor, not a dealbreaker |

## Scoring method

Each factor uses **Jaccard similarity** (intersection / union) or a
simple distance-based decay:

- **Availability**: time slots are expanded into `(day, hour)` units;
  overlap / union of both users' slot sets.
- **Course overlap**: overlap / union of enrolled course IDs.
- **Study style**: exact match = 1.0, otherwise 0.0 (simple by design —
  can be upgraded to a similarity table later, e.g. "quiet" and
  "flashcards" being partially compatible, without changing the public
  `calculate_score()` interface).
- **Pace**: linear decay based on distance on a 1–5 scale.

Final score = weighted sum × 100, rounded to 1 decimal place.

## Properties worth knowing (and are tested)

- **Symmetric**: `calculate_score(a, b) == calculate_score(b, a)` —
  verified in `tests/test_scoring.py`.
- **Bounded**: always falls between 0 and 100.
- **Self-scoring raises an error** rather than silently returning a
  meaningless number.

## Complexity note

Ranking a user against N candidates is O(N) per user, and scoring the
entire pool pairwise is O(N²). Fine at class-project scale; at real
scale, the first optimization would be pre-filtering by shared course
before scoring, since two students with zero course overlap are
extremely unlikely to be a good match anyway.

## Explainability

`explain_match(user1, user2)` returns the score alongside human-readable
reasons (e.g. "3 overlapping study time blocks", "Same study style
(quiet)"), so the frontend doesn't have to show a bare number.
