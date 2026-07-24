# Study Partner Backend

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then fill in real Google + Notion OAuth credentials
python run.py
```

Server runs at `http://localhost:5000`. Sanity check: visit
`http://localhost:5000/api/match/ping` — you should see
`{"status": "match blueprint alive"}`.

## Getting Google OAuth credentials

1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new project (or use an existing one)
3. Configure the OAuth consent screen (External, testing mode is fine for now)
4. Create an "OAuth 2.0 Client ID" of type "Web application"
5. Add `http://localhost:5000/api/auth/google/callback` as an authorized redirect URI
6. Copy the Client ID and Client Secret into your `.env` file
7. Enable the "Google Calendar API" for the project under "Enabled APIs & Services"

## Getting Notion OAuth credentials

1. Go to https://www.notion.so/my-integrations
2. Create a new "Public integration" (needed for the OAuth flow, not an internal integration)
3. Add `http://localhost:5000/api/auth/notion/callback` as the redirect URI
4. Copy the OAuth client ID and client secret into your `.env` file
5. In Notion, share a parent page with the integration — its page ID is the
   `notion_parent_page_id` that `/api/match/confirm` needs to create shared
   study-notes pages under

## Project structure

```
app/
  config.py               # all env-var based settings, read once here
  __init__.py              # app factory (create_app) — wires everything together
  database/
    db.py                  # the single shared SQLAlchemy instance
    migrations.py          # init_db() / reset_db() — create_all()/drop_all() wrappers
    seed.py                 # demo data: python -m app.database.seed (destructive reset!)
  models/
    oauth_token.py         # per-user OAuth tokens, user_id FKs to User
    user.py, course.py, availability.py, preference.py, match.py
  services/
    google_calendar_service.py  # Google OAuth + Calendar event/Meet link creation
    notion_service.py           # Notion OAuth + shared study-notes page creation
    scoring.py, ranking.py      # compatibility scoring math (course/availability/style/pace)
    recommendation_engine.py    # stable facade routes should import from — calculate_score, explain_match
    persistence.py              # DB read/write helpers (save_match, get_user, ...)
    matching_service.py         # superseded by recommendation_engine.py; kept for its own tests only
  routes/
    auth_routes.py          # Google + Notion OAuth login/callback endpoints
    match_routes.py          # /api/match/confirm — scores a real pair, books Calendar + Notion, persists Match
run.py                       # entry point — python run.py
```

The database schema (`User`/`Course`/`Availability`/`Preference`/`Match`) and
the compatibility scoring algorithm (`scoring.py`/`ranking.py`/
`recommendation_engine.py`) were designed and built by Manuel — this backend
wires them into the OAuth/Calendar/Notion flow rather than replacing them.

## What's implemented

- Google Calendar OAuth (login, callback, token refresh) + event creation with
  an auto-generated Meet link
- Notion OAuth (login, callback with CSRF state validation) + shared study
  page creation
- Compatibility scoring: weighted availability/course/study-style/pace score
  against real `User` DB rows (`app/services/recommendation_engine.py`)
- `POST /api/match/confirm` — looks up `user_id`/`partner_id` as real users,
  scores them, tries to book a Calendar event and a Notion page (either can
  be missing or fail without blocking confirmation — `calendar_status`/
  `notion_status` reflect what actually happened), then persists a `Match`
  row and returns its `match_id`.

## Known gap

`Match` only stores `user_a_id`/`user_b_id`/`score`/`status` — the Calendar/
Notion outcome (`calendar_status`, `meet_link`, `notion_status`,
`notes_page_url`) is returned in the response but not persisted, so a later
re-fetch of a past match loses that detail. Extending `Match` with nullable
columns for those fields is a natural next step.

## Testing

```bash
pip install -r requirements.txt   # includes pytest
python -m pytest tests/ -v
```

34 tests cover availability/compatibility scoring, ranking, DB persistence
(`Match`/`User` CRUD), and the `/api/match/confirm` route (success + real
persisted `Match`, incompatible pair, unknown user, Calendar/Notion failure
fallback paths).

Manual check: after setting up OAuth credentials above and seeding at least
two `User` rows (see `app/database/seed.py`, or `app/services/persistence.py`'s
`create_user`/`add_availability`/`set_preference`/`enroll_user_in_course`),
visit `/api/auth/google/login` and `/api/auth/notion/login` in a browser to
connect each account, then hit `/api/match/confirm` with real `user_id`/
`partner_id` values per the docstring in `match_routes.py`.
