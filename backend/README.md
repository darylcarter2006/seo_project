# Study Partner Backend

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then fill in real Google OAuth credentials
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

## Project structure

```
app/
  config.py              # all env-var based settings, read once here
  __init__.py             # app factory (create_app) — wires everything together
  models/
    oauth_token.py        # DB table storing per-user OAuth tokens
  services/
    google_calendar_service.py   # ALL Google OAuth + Calendar API logic
  routes/
    auth_routes.py         # HTTP endpoints for the OAuth flow (thin — calls the service)
    match_routes.py        # matching + booking endpoints (mostly stubbed, fill in Day 2/3)
run.py                     # entry point — python run.py
```

## Status: what's stubbed vs done

Everything is scaffolded with docstrings explaining what to do, but the
actual logic (marked `pass` / `TODO`) still needs to be written. This is
intentional — filling these in is how you actually learn OAuth instead of
copy-pasting a working version.

Build order:
1. `GoogleCalendarService.get_authorization_url()` — build the "connect"
   link
2. `auth_routes.google_login()` — wire that into a route
3. `GoogleCalendarService.exchange_code_for_tokens()` — handle the
   callback's `code` param
4. `auth_routes.google_callback()` — save the tokens to the DB
5. `OAuthToken.is_expired()` — small helper, do this early, it's easy
6. `GoogleCalendarService.refresh_access_token()` — handles expired tokens
7. `auth_routes.get_valid_access_token()` — ties expiry check + refresh together
8. `GoogleCalendarService.create_calendar_event()` — actually books the event

Test as you go: after step 4, you should be able to visit
`/api/auth/google/login` in a browser, approve access, and see
`{"status": "connected"}`. Don't move on to step 5+ until that works.
