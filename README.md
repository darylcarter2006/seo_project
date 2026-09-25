# StudySync

[![Tests](https://github.com/darylcarter2006/seo_project/actions/workflows/tests.yml/badge.svg)](https://github.com/darylcarter2006/seo_project/actions/workflows/tests.yml)

StudySync matches students who are in the same course and have overlapping free time, then handles the logistics: it sends a two-sided invite, and once the partner accepts it books a Google Calendar event with a Google Meet link and creates a Notion study-notes page.

It is a team project built as a Flask REST API with a static HTML/CSS/JavaScript frontend.

## What it does

1. **Create a profile.** Name, email, course, weekly availability, and optional study style and pace.
2. **Browse ranked matches.** Classmates at the same school are scored for compatibility. Each result shows the score, the reasons behind it, and the exact time windows both people are free.
3. **Propose a session.** The proposer picks a time and topic. This sends a pending invite and books nothing yet.
4. **Partner accepts or declines.** Only the invited partner can respond. On accept, the app creates a Google Calendar event (both people invited, Meet link included) and a Notion notes page.
5. **Manage sessions.** A dashboard shows pending and sent invites and confirmed sessions with the partner's contact info. Either participant can cancel, which also deletes the Calendar event.

## Tech stack

| Area | Tools |
|---|---|
| Backend | Python 3.12, Flask 3, Flask-SQLAlchemy, SQLite (swappable via `DATABASE_URL`) |
| Integrations | Google OAuth 2.0 and Calendar API, Notion OAuth and API |
| Frontend | Static HTML, CSS, vanilla JavaScript (no build step) |
| Testing / CI | pytest (92 tests), GitHub Actions on every push and PR to `main` |

## Engineering highlights

- **Weighted recommendation engine.** Compatibility combines availability overlap (45%), shared courses (25%), study style (20%), and pace (10%). Each factor is normalized to 0–1 using Jaccard similarity or distance decay. Scores are symmetric, bounded to 0–100, and come with human-readable explanations. See [`backend/docs/recommendation.md`](backend/docs/recommendation.md).
- **Two-sided confirmation workflow.** The original flow booked resources on the initiator's say-so alone. I reworked it into propose, then accept or decline, with authorization checks (403 for the wrong user, 400 for an already-answered invite). Session details live in a separate `MatchProposal` table so the core `Match` schema stayed untouched.
- **OAuth done carefully.** Google token refresh, and CSRF `state` validation on the Notion flow. Redirects return the user to the app instead of leaving them on a raw JSON page.
- **Graceful degradation.** A missing connection or a failed Calendar/Notion call never blocks accepting or cancelling a match. The outcome is stored (`calendar_status`, `notion_status`, `meet_link`) and shown to the user.
- **Actual overlap windows, not just a count.** Contiguous free hours are merged into blocks such as `monday 14:00–16:00`, so users can see when to meet.
- **Documented limits.** Some constraints are written down rather than hidden. Examples: the Notion public API can't grant page access to another user, school scoping uses email domain as a stand-in for a school field, and user identification is a stopgap rather than real auth. See [`backend/README.md`](backend/README.md).
- **Tested and automated.** The suite covers scoring, ranking, persistence, every match route (propose, respond, cancel, dismiss, history), the OAuth redirects, and seed-script idempotency.

## Architecture

```
frontend/                      Static pages: profile, matches, dashboard
  api.js                       Backend client helpers
backend/
  run.py                       Entry point
  app/
    __init__.py                App factory (create_app)
    config.py                  Env-based settings
    models/                    User, Course, Availability, Preference, Match, MatchProposal, OAuthToken
    routes/                    auth_routes, match_routes, user_routes
    services/                  scoring, ranking, recommendation_engine,
                               google_calendar_service, notion_service, persistence
    database/                  db setup, init/reset helpers, demo seed data
  docs/                        schema.md, recommendation.md
  tests/                       pytest suite
```

## API overview

| Endpoint | Purpose |
|---|---|
| `POST /api/users` | Create or update a profile (looked up by email) |
| `GET /api/users/<id>/connections` | Which OAuth providers the user has connected |
| `GET /api/match/candidates?user_id=` | Ranked same-school candidates with overlap windows |
| `POST /api/match/confirm` | Propose a match (creates a pending invite) |
| `POST /api/match/<id>/respond` | Partner accepts or declines; accept books Calendar and Notion |
| `POST /api/match/<id>/cancel` | Cancel a confirmed match and delete the Calendar event |
| `GET /api/match/pending`, `/sent`, `/history` | Invites to answer, invites sent, confirmed sessions |
| `GET /api/auth/google/login`, `/api/auth/notion/login` | Start the OAuth flows |

## Run it locally

Requires Python 3.12 or later.

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add Google and Notion OAuth credentials (optional for browsing matches)
python -m app.database.seed     # 10 demo users with varied availability
python run.py                   # http://localhost:5000

# Frontend (second terminal)
cd frontend
python -m http.server 8000      # open http://localhost:8000/profile.html
```

Use an `@example.edu` email to see the seeded demo users as candidates. Steps for creating Google and Notion OAuth credentials are in [`backend/README.md`](backend/README.md).

## Run the tests

```bash
cd backend
python -m pytest tests -v
```

## Team

- **Daryl Carter** built the Flask backend: Google Calendar and Notion OAuth and booking, the two-sided match workflow, the match, user, and auth endpoints, frontend-to-backend wiring, seed data, and the CI pipeline.
- **Manuel Arellano Jr.** designed the database schema and the recommendation and scoring engine.
- **Abdul (abduln611)** built the frontend pages and styling.

## Known limitations

This is a internship-project-scale app, not a production service. There is no real authentication yet, CORS is open for local development, and there is no migrations tool. These are documented in detail in [`backend/README.md`](backend/README.md).

## License

MIT. See [LICENSE](LICENSE).
