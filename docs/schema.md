# Database Schema

## Tables

**User** — `id, name, email, created_at`
Central entity. Has many `Availability` slots, one `Preference`, and a
many-to-many relationship to `Course`.

**Course** — `id, name, code`
Linked to `User` via the `user_courses` join table (many-to-many: a
student takes multiple courses, a course has many students).

**Availability** — `id, user_id, day_of_week, start_hour, end_hour`
One row per free-time block. `day_of_week` is 0=Monday...6=Sunday.
Hour-granularity integers, not datetimes — sufficient for matching,
simple to reason about and test.

**Preference** — `id, user_id (unique), study_style, pace`
One-to-one with `User`. Kept as its own table (not columns on `User`) so
it can be extended later without touching the core `User` model.
`pace` is an integer 1 (relaxed) – 5 (intensive).

**Match** — `id, user_a_id, user_b_id, score, status, created_at`
Stores the score at the time of matching plus a status
(`pending`/`confirmed`/`declined`), so match history is preserved even
if either user's data changes later.

## Key design decisions

- **Availability is its own table, not a column**, because a student can
  have multiple free-time blocks across different days — a single-column
  representation couldn't express that.
- **`user_courses` is a plain join table**, not a model with its own
  identity, because it currently carries no data beyond the relationship
  itself (no "enrollment date" etc. yet).
- **Match stores the score, not just the pair**, so historical matches
  don't silently change if the scoring algorithm or weights are tuned
  later — this is a deliberate audit-trail choice.
