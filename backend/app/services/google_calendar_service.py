"""
app/services/google_calendar_service.py
-----------------------------------------
Handles everything related to talking to Google's OAuth + Calendar API.

The OAuth flow, at a high level, works like this:

    1. User clicks "Connect Google Calendar" in the frontend.
    2. We redirect them to Google's consent screen (get_authorization_url).
    3. User approves. Google redirects back to OUR callback route with a
       one-time-use "code" in the URL.
    4. We exchange that code for an access_token + refresh_token
       (exchange_code_for_tokens).
    5. We store both tokens in the DB (see OAuthToken model).
    6. Later, whenever we need to call the Calendar API, we check if the
       access_token is expired. If it is, we use the refresh_token to get
       a new one (refresh_access_token) before making the call.

Docs you'll want open while building this:
    https://developers.google.com/identity/protocols/oauth2/web-server
    https://google-auth-oauthlib.readthedocs.io/
    https://developers.google.com/calendar/api/v3/reference/events/insert
"""

from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from datetime import datetime, timedelta

from app.config import Config


class GoogleCalendarService:
    """
    Wraps all Google Calendar OAuth + API logic in one place so routes
    stay thin (routes should just call these methods, not contain
    OAuth/API logic themselves).
    """

    @staticmethod
    def get_authorization_url():
        """
        Build the URL we redirect the user to so they can approve access
        to their Google Calendar.

        Steps to implement:
        1. Create a `Flow` object using Flow.from_client_config(...).
           You'll need a client_config dict shaped like:
               {
                   "web": {
                       "client_id": Config.GOOGLE_CLIENT_ID,
                       "client_secret": Config.GOOGLE_CLIENT_SECRET,
                       "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                       "token_uri": "https://oauth2.googleapis.com/token",
                       "redirect_uris": [Config.GOOGLE_REDIRECT_URI],
                   }
               }
        2. Set flow.redirect_uri = Config.GOOGLE_REDIRECT_URI
        3. Call flow.authorization_url(access_type="offline", prompt="consent")
           - access_type="offline" is REQUIRED to get a refresh_token back.
             Without it, Google only gives you a short-lived access_token
             and you'll be stuck re-authenticating constantly.
           - prompt="consent" forces the consent screen every time, useful
             while testing so you always get a fresh refresh_token.
        4. authorization_url() returns a tuple: (url, state).
           Return both — you'll want to stash `state` in the Flask session
           in the route, so you can verify the callback isn't forged.

        Returns:
            tuple: (authorization_url: str, state: str)
        """
        pass

    @staticmethod
    def exchange_code_for_tokens(code):
        """
        Exchange the one-time authorization `code` Google sent back to our
        callback route for real tokens.

        Steps to implement:
        1. Rebuild the same Flow object as in get_authorization_url()
           (same client_config, same redirect_uri).
        2. Call flow.fetch_token(code=code)
        3. Pull the credentials off flow.credentials — it has:
             .token           -> the access token
             .refresh_token   -> the refresh token (may be None if the
                                  user already granted consent before and
                                  Google didn't resend it!)
             .expiry          -> a datetime of when the access token expires

        Returns:
            dict: {
                "access_token": str,
                "refresh_token": str or None,
                "expires_at": datetime,
            }
        """
        pass

    @staticmethod
    def refresh_access_token(refresh_token):
        """
        Use a stored refresh_token to get a brand new access_token, without
        making the user log in again. Call this before any API request if
        OAuthToken.is_expired() is True.

        Steps to implement:
        1. Build a `Credentials` object manually (google.oauth2.credentials.Credentials)
           using the refresh_token, client_id, client_secret, and token_uri.
        2. Call creds.refresh(GoogleRequest())  — this hits Google's token
           endpoint and populates creds.token with a new access token.
        3. IMPORTANT: wrap this in a try/except. If the refresh_token itself
           has been revoked (user removed access in their Google account,
           or it just expired from disuse), this will raise an exception.
           On failure, you should signal that the user needs to
           re-authenticate from scratch (this is the "design for failure"
           story worth mentioning in your presentation).

        Returns:
            dict: {"access_token": str, "expires_at": datetime}
            or None if the refresh failed (caller should handle this by
            prompting re-auth).
        """
        pass

    @staticmethod
    def create_calendar_event(access_token, summary, start_time, end_time, attendee_emails=None):
        """
        Create a study session event on the user's Google Calendar.
        Called after two students are matched, to actually book the time.

        Steps to implement:
        1. Build a Credentials object from the access_token
           (google.oauth2.credentials.Credentials(token=access_token)).
        2. Build the API client: build("calendar", "v3", credentials=creds)
        3. Construct the event body dict, e.g.:
               {
                   "summary": summary,
                   "start": {"dateTime": start_time.isoformat(), "timeZone": "America/New_York"},
                   "end": {"dateTime": end_time.isoformat(), "timeZone": "America/New_York"},
                   "attendees": [{"email": e} for e in (attendee_emails or [])],
               }
        4. Call service.events().insert(calendarId="primary", body=event).execute()
        5. Wrap the whole thing in try/except — this is your "design for
           failure" moment. If this raises (network issue, expired token,
           rate limit), catch it and return None instead of crashing the
           whole match-confirmation flow. The route calling this should
           check for None and show the user a "we'll confirm shortly"
           message rather than a 500 error.

        Returns:
            dict: the created event's data from Google (includes an "id"
            and "htmlLink" you can show the user), or None on failure.
        """
        pass
