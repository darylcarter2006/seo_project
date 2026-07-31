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
    match_proposal.py      # session details (start/end/topic/notion page) for a pending Match
  services/
    google_calendar_service.py  # Google OAuth + Calendar event/Meet link creation
    notion_service.py           # Notion OAuth + shared study-notes page creation
    scoring.py, ranking.py      # compatibility scoring math (course/availability/style/pace)
    recommendation_engine.py    # stable facade routes should import from — calculate_score, explain_match
    persistence.py              # DB read/write helpers (save_match, get_user, ...)
    matching_service.py         # superseded by recommendation_engine.py; kept for its own tests only
  routes/
    auth_routes.py          # Google + Notion OAuth login/callback endpoints
    match_routes.py          # /api/match/confirm, /<id>/respond, /<id>/cancel, /pending, /sent, /candidates, /history
    user_routes.py           # POST /api/users, GET /<id>/connections
run.py                       # entry point — python run.py
```

The frontend (`../frontend/profile.html`, `../frontend/dashboard.html`,
`../frontend/matches.html`, `../frontend/api.js`, `../frontend/styles.css`)
is static HTML with no build step. It's cross-origin from this API (opened
via `file://` or a separate static server), so `app/__init__.py` sets
permissive dev-only CORS headers (`Access-Control-Allow-Origin: *`) —
every request already carries an explicit `user_id` rather than relying
on cookies, so this doesn't expose anything a same-origin request
wouldn't. Not meant for production.

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
- `POST /api/match/confirm` — **proposes** a match between two existing
  users as a `status="pending"` invite. Does not book anything yet. See
  "Two-sided match confirmation" below.
- `POST /api/match/<match_id>/respond` — only the invited partner may
  accept or decline a pending match. Declining just marks it `declined`.
  Accepting is where the Calendar event (inviting the partner as a real
  attendee) and Notion page actually get created now, with the same
  graceful-degradation as before (`calendar_status`/`notion_status`
  reflect what actually happened; a missing connection or failed API call
  never blocks acceptance).
- `POST /api/match/<match_id>/cancel` — either participant can cancel a
  `confirmed` match (403 for a non-participant, 400 if it isn't currently
  confirmed). Best-effort deletes the actual Google Calendar event using
  the event id captured at accept time; a missing event id, missing
  connection, or failed delete never blocks cancellation, just shows up
  as `calendar_event_deleted: false` in the response. Sets `status="cancelled"`.
- `GET /api/match/pending?user_id=` — invites waiting on this user to
  accept/decline (matches where they're the invited side and still
  pending), for `dashboard.html`'s "Pending invites" section.
- `GET /api/match/sent?user_id=` — invites this user proposed that are
  still awaiting the other person's response (the mirror image of
  `/pending` — matches where they're the proposer, not the invited side),
  for `dashboard.html`'s "Sent invites" section, so a proposer isn't left
  with zero visibility into invites they sent.
- `POST /api/users` — creates or updates a profile (name, email, a single
  course code, weekly availability, optional study style/pace) from the
  shape `profile.html`'s form actually submits. Looked up by email, so
  resubmitting the same email updates that user instead of duplicating.
  `profile.html` also has an "Apply one time range to all checked days"
  bulk-fill control above the per-day fields, purely client-side (fills
  the same per-day inputs `buildAvailability()` already reads — no new
  request shape).
- `GET /api/users/<user_id>/connections` — which OAuth providers
  (`google_calendar`, `notion`) this user currently has a valid connection
  for, so `profile.html` can show "✓ connected" instead of a plain
  "Connect" button regardless of prior state.
- `GET /api/match/candidates?user_id=` — ranked list of other users at the
  same school (see "Design decision" below) for `matches.html` to render,
  via `recommendation_engine.find_best_matches()`. Each candidate includes
  `overlapping_availability`: the actual overlapping time windows (not
  just a count), e.g. `[{"day": "monday", "start": "14:00", "end": "16:00"}]`,
  computed by `scoring.overlapping_windows()` (merges contiguous
  overlapping hours into single blocks) so the frontend can show exactly
  when to schedule instead of guessing. Note: it ranks *everyone* within
  that school, including 0-score pairs — there's no minimum-score cutoff,
  so very low/no-overlap candidates still appear, just last.
- `GET /api/match/history?user_id=` — this user's **confirmed** matches
  (i.e. the invited partner actually accepted), including `partner_email`
  alongside `partner_name` so `dashboard.html` can show a way to actually
  contact your matched partner directly instead of digging through the
  Calendar invite email — the schema has no multi-person "group" concept,
  so this shows 1:1 sessions.

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

## Two-sided match confirmation

Confirming a match used to immediately book the Calendar/Notion resources
on the initiator's say-so alone — the partner had no say, and their email
was never even added to the Calendar event (`attendee_emails` sat empty
since the endpoint was first built). That's now a two-step flow:

1. `POST /api/match/confirm` proposes the match: validates compatibility
   exactly as before, then saves a `status="pending"` `Match` row plus a
   `MatchProposal` row holding the session details (`start_time`,
   `end_time`, `topic`, `notion_parent_page_id`) for later. Nothing is
   booked.
2. The invited partner calls `POST /api/match/<match_id>/respond` with
   `{"response": "accept"}` or `{"response": "decline"}`. Only they can
   respond (403 otherwise) and only while it's still pending (400 if
   already responded to). Declining sets `status="declined"`. Accepting
   is when the Calendar event and Notion page actually get created,
   pulling the session details back out of `MatchProposal` — and this
   time `attendee_emails` includes the accepting partner's real email, so
   both people actually get invited.

`MatchProposal` (`app/models/match_proposal.py`) is a small new table, not
new columns on `Match` — `Match`'s schema belongs to Manuel and stays
untouched; this is purely additive and only exists to bridge the gap
between proposing a session time and actually needing it at accept time.
It also stores `google_calendar_event_id` once a Calendar event is
successfully booked, for the same "don't touch `Match`" reason — this is
what `POST /api/match/<match_id>/cancel` uses to actually delete the
Calendar event later, not just flip a status in our own DB.

**Dev note:** `MatchProposal` gained the `google_calendar_event_id` column,
and later `calendar_status`/`meet_link`/`notion_status`/`notes_page_url`,
after some of you may have already created `instance/study_partner.db` —
there's no migrations tool here (see `migrations.py`'s docstring), so if
you hit a "no such column" error, delete that sqlite file and let
`init_db()` recreate it (or re-run `python -m app.database.seed` after).

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

## Who's logged in

Since there's no login system, `profile.html`, `dashboard.html`, and
`matches.html` all show a small "Logged in as {name}" line under the
masthead (or "No profile yet"), reading from the same `getStoredProfile()`
`localStorage` helper everything else already uses — purely so a live
demo with multiple people isn't confusing about whose view is on screen.
No backend involved.

## Explicit profile loading (no more auto-prefill)

`profile.html` used to prefill the name/email/course/availability fields
from a single shared `localStorage` key (`studyProfile`) on every page
load. That was a real problem on a shared browser: since `POST /api/users`
looks up users by email to decide create-vs-update, a second person could
fill out the form without noticing a first person's email was still
sitting in the `email` field, and submitting would **silently overwrite
the first person's profile** instead of creating a second one. This bit
us once during testing.

Root fix, not just a mitigation: the form **no longer auto-prefills from
localStorage at all**. A brand-new person on the same browser now just
gets a blank form, full stop. If `studyUserId` is set (i.e. this browser
has saved a profile before), a "Load my saved profile" link appears; only
when clicked does it call the new `GET /api/users/<user_id>` endpoint and
populate the form from that authoritative backend response — never from
the local snapshot. The "New profile / not you?" link is still there as
an explicit reset/fallback, but it's no longer the thing standing between
a user and silently overwriting someone else's data — not auto-loading in
the first place is.

## Booking-outcome persistence

The Calendar/Notion outcome from accepting a match (`calendar_status`,
`meet_link`, `notion_status`, `notes_page_url`) is saved onto the
`MatchProposal` row (`persistence.save_booking_result()`) right after
`_book_session()` runs in `/respond`'s accept path, and `GET
/api/match/history` reads it back from there for each confirmed match.
Same "don't touch `Match`'s schema" reasoning as everything else on
`MatchProposal` — this used to only exist in the one-time `/respond`
response and was lost on any later re-fetch.

## Known limitation: "shared" Notion notes aren't actually shared access

`notion_service.create_shared_page()` creates the study-notes page inside
the **proposer's own Notion workspace**, using only their OAuth token
(`parent_page_id` has to be a page they personally own and connected the
integration to — Notion requires a parent). Both participants get shown
the resulting `notes_page_url` on their Dashboard, but that's just a
link — it does **not** mean the invited partner has been granted access.

We checked developers.notion.com directly before deciding this was worth
a real fix vs. a documented limitation: **the public Notion API has no
endpoint to programmatically add a collaborator/guest to a page, share a
page by email, invite a non-workspace-member, or make a page public.**
The Users API is read-only (`GET /v1/users`, `GET /v1/users/me` — no
create/invite operations), and the one provisioning mechanism that does
exist, SCIM, is Enterprise-plan-only workspace user provisioning, not
page-level access granting, and isn't a fit here regardless.

So "shared" currently means: the page is created once, in the proposer's
workspace, and the same link is surfaced to both people. Whether the
invited partner can actually open it depends entirely on the proposer's
own manual Notion sharing settings for that parent page (e.g. "Share to
web," or explicitly inviting the partner's Notion account by hand) —
something this app has no way to set on their behalf. The Dashboard link
now says as much (`frontend/dashboard.html`) instead of implying
guaranteed shared access.

## Testing

```bash
pip install -r requirements.txt   # includes pytest
python -m pytest tests/ -v
```

81 tests cover availability/compatibility scoring and overlapping-window
computation, ranking, DB persistence (`Match`/`User` CRUD), profile
creation/update (`POST /api/users`), connection status, match discovery
including the same-school hard filter and `partner_email` (`/candidates`,
`/history`, `/pending`, `/sent`), the OAuth `user_id` query param and
redirect-on-callback behavior, the seed script's idempotency, proposing a
match (pending, books nothing), the full accept/decline flow (`/respond`)
including the wrong-responder 403, already-responded 400, and the
partner's email landing in `attendee_emails` on accept, and cancelling a
confirmed match (`/cancel`) including the best-effort Calendar-delete
paths (succeeds, fails, no stored event id) and the non-participant 403.

Manual check, full 3-tab flow: run `python -m app.database.seed` to get demo
users in place, then `python run.py`, then serve the frontend statically
from the `frontend/` directory (e.g. `cd ../frontend && python -m http.server 8000`)
and open `http://localhost:8000/profile.html` — create a profile with an
`@example.edu` email so it's visible to the seeded demo users, or just log
in as one of them directly. The Matches tab fetches real (same-school)
candidates (with actual overlap windows) from `/api/match/candidates`;
proposing one sends a pending invite, visible on the proposer's own
Dashboard tab under "Sent invites" and on the partner's Dashboard tab
under "Pending invites" (with Accept/Decline) until they respond, then it
shows up as confirmed via `/api/match/history` (with a Cancel button and
the partner's email) on both.
