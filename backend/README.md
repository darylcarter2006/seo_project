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
  models/
    oauth_token.py         # DB table storing per-user OAuth tokens
  services/
    google_calendar_service.py  # Google OAuth + Calendar event/Meet link creation
    notion_service.py           # Notion OAuth + shared study-notes page creation
    matching_service.py         # course + availability compatibility scoring
  routes/
    auth_routes.py          # Google + Notion OAuth login/callback endpoints
    match_routes.py          # /api/match/confirm — scores a pair, books Calendar + Notion
run.py                       # entry point — python run.py
```

## What's implemented

- Google Calendar OAuth (login, callback, token refresh) + event creation with
  an auto-generated Meet link
- Notion OAuth (login, callback with CSRF state validation) + shared study
  page creation
- Compatibility scoring: course match + availability overlap
  (`app/services/matching_service.py`)
- `POST /api/match/confirm` — validates a proposed pair is compatible, then
  tries to book a Calendar event and a Notion page. Either integration can be
  missing or fail without blocking match confirmation (the response's
  `calendar_status`/`notion_status` fields reflect what actually happened).

## Known gap

DB persistence for the `Match` record itself isn't wired up yet — the
`Student`/`Availability`/`Match` schema is still pending from the team. See
the `TODO` in `match_routes.py::confirm_match` for the shape it should take
once that schema lands.

## Testing

```bash
python -m unittest discover tests -v
```

12 tests cover availability overlap, compatibility scoring, and the
`/api/match/confirm` route (success, incompatible pair, and Calendar/Notion
failure fallback paths).

Manual check: after setting up OAuth credentials above, visit
`/api/auth/google/login` and `/api/auth/notion/login` in a browser to connect
each account, then hit `/api/match/confirm` with a JSON body per the docstring
in `match_routes.py`.
