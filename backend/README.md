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
    seed.py                 # demo data: python -m app.database.seed (safe to re-run, see below)
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
    match_routes.py          # /api/match/confirm, /candidates, /history
    user_routes.py           # POST /api/users — create/update a profile
run.py                       # entry point — python run.py
```

The frontend (`../profile.html`, `../dashboard.html`, `../matches.html`,
`../api.js`, `../styles.css`) is static HTML with no build step. It's
cross-origin from this API (opened via `file://` or a separate static
server), so `app/__init__.py` sets permissive dev-only CORS headers
(`Access-Control-Allow-Origin: *`) — every request already carries an
explicit `user_id` rather than relying on cookies, so this doesn't expose
anything a same-origin request wouldn't. Not meant for production.

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
- `POST /api/users` — creates or updates a profile (name, email, a single
  course code, weekly availability, optional study style/pace) from the
  shape `profile.html`'s form actually submits. Looked up by email, so
  resubmitting the same email updates that user instead of duplicating.
- `GET /api/match/candidates?user_id=` — ranked list of other users at the
  same school (see "Design decision" below) for `matches.html` to render,
  via `recommendation_engine.find_best_matches()`. Note: it ranks
  *everyone* within that school, including 0-score pairs — there's no
  minimum-score cutoff, so very low/no-overlap candidates still appear,
  just last.
- `GET /api/match/history?user_id=` — this user's confirmed matches, for
  `dashboard.html`'s "Your groups" section (repurposed to show real
  confirmed 1:1 matches — the schema has no multi-person "group" concept).

## Temporary user identification (not real auth)

There's no login system yet. `/api/auth/google/login` and
`/api/auth/notion/login` accept an optional `?user_id=` query param
(falls back to `1` if omitted), which the frontend passes after a profile
is saved so OAuth tokens attach to the right user. **This is not a
security measure** — nothing stops a request from claiming any `user_id`.
Real auth (or at minimum an email-based lookup/magic link) is the natural
next step once there's time.

After the OAuth redirect completes (success or failure), the backend sends
the browser back to `{FRONTEND_BASE_URL}/profile.html` (configurable via
the `FRONTEND_BASE_URL` env var, default `http://localhost:8000`, dev-only)
with `?connected=google`/`?connected=notion` or `?connection_error=1`,
which `profile.html` reads on load to show a status message — instead of
leaving the user stranded on a bare JSON response.

## Design decision: school-scoping by email domain

`GET /api/match/candidates` never shows a candidate whose email domain
(the part after `@`, via `persistence.email_domain()`) doesn't match the
requester's — a `chem101@bigstate.edu` user and a `chem101@othercollege.edu`
user typing the same course code aren't in the same class, and shouldn't
match just because the text matches.

**Why email domain:** there's no dedicated "school" field on `User` (adding
one is a real schema change to Manuel's model, out of scope here), but
every profile already requires a real email — the domain is a reasonable
free proxy for "same institution" with zero schema changes.

**Why a hard filter, not a ranking signal:** a cross-school "match" isn't a
worse match, it's not a match at all — they can't actually be in the same
class. Demoting it with a lower score would still let it appear in the
list; excluding it entirely from `get_all_users()` before scoring is what
actually prevents it from ever showing up.

**Known limitation:** this breaks down for schools that share a generic
email provider (e.g. two students both on `@gmail.com`, or a school that
issues `@outlook.com` addresses) — they'd either be wrongly excluded from
real classmates using a different address, or wrongly included with
strangers on the same generic provider. A real `school_id` field (or a
domain allowlist keyed to actual institutions) is the correct long-term
fix; email domain is a deliberate stopgap given the timeline.

## Demo seed data

```bash
python -m app.database.seed
```

Creates/updates 10 demo users, all `@example.edu` (so they're mutually
visible to each other under the school-scoping above), across 5 courses
with deliberately varied availability/study-style/pace so browsing
candidates for any one of them shows a realistic mix of high, medium, and
low match scores instead of a uniform wall of 100%s or 0%s. See the
clustering comment at the top of `app/database/seed.py` for the reasoning
behind each grouping.

**Safe to re-run**: each user is looked up and updated by email rather than
duplicated, and — unlike the old version of this script — it does **not**
wipe the database first (`init_db()`'s idempotent `create_all()`, not
`reset_db()`'s `drop_all()`), so anything else in the DB (OAuth tokens,
matches you confirmed by hand while testing) survives a re-seed.

To try it: run the seed script, then hit `/api/match/candidates?user_id=1`
(Ava Chen is seeded first, so she'll typically get id `1` on a fresh DB —
confirm the actual id via `sqlite3 instance/study_partner.db "select id, email from user;"`
if you've seeded before) and you should see a spread of scores, not all-or-nothing.

## Known UX limitation: stale profile-form data between users

`profile.html` prefills the name/email/course/availability fields from a
single shared `localStorage` key (`studyProfile`) on load, for the
legitimate case of editing your own existing profile. It does **not**
auto-clear between different people using the same browser — since
`POST /api/users` looks up users by email to decide create-vs-update, if a
second person fills out the form without noticing a first person's email
is still sitting in the `email` field, submitting **silently overwrites
the first person's profile** instead of creating a second one. This bit us
once during testing.

Mitigation shipped: a visible "New profile / not you?" link (top of the
Profile tab and next to the email field) that explicitly clears the form
and the `studyProfile`/`studyUserId` localStorage keys, plus an inline
warning by the email field. It is **not** automatic — auto-clearing on
every page load would break the "edit my own profile" case — so a user
who doesn't click it can still hit this. When demoing with multiple
people on one laptop, always click "New profile / not you?" before
handing the keyboard to the next person.

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

57 tests cover availability/compatibility scoring, ranking, DB persistence
(`Match`/`User` CRUD), profile creation/update (`POST /api/users`), match
discovery including the same-school hard filter (`/candidates`, `/history`),
the OAuth `user_id` query param and redirect-on-callback behavior, the seed
script's idempotency, and `/api/match/confirm` (success + real persisted
`Match`, incompatible pair, unknown user, Calendar/Notion failure fallback
paths).

Manual check, full 3-tab flow: run `python -m app.database.seed` to get demo
users in place, then `python run.py`, then serve the frontend statically
from the repo root (e.g. `python -m http.server 8000`) and open
`http://localhost:8000/profile.html` — create a profile with an
`@example.edu` email so it's visible to the seeded demo users, or just log
in as one of them directly. The Matches tab fetches real (same-school)
candidates from `/api/match/candidates`; confirming one shows up on the
Dashboard tab via `/api/match/history`.
