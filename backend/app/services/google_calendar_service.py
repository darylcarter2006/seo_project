import uuid

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

from app.config import Config


class GoogleCalendarService:

    @staticmethod
    def _build_client_config():
        return {
            "web": {
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [Config.GOOGLE_REDIRECT_URI],
            }
        }

    @staticmethod
    def get_authorization_url():
        client_config = GoogleCalendarService._build_client_config()
        flow = Flow.from_client_config(client_config, scopes=Config.GOOGLE_SCOPES)
        flow.redirect_uri = Config.GOOGLE_REDIRECT_URI

        auth_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )
        return auth_url, state

    @staticmethod
    def exchange_code_for_tokens(code):
        client_config = GoogleCalendarService._build_client_config()
        flow = Flow.from_client_config(client_config, scopes=Config.GOOGLE_SCOPES)
        flow.redirect_uri = Config.GOOGLE_REDIRECT_URI

        flow.fetch_token(code=code)
        creds = flow.credentials

        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "expires_at": creds.expiry,
        }

    @staticmethod
    def refresh_access_token(refresh_token):
        try:
            creds = Credentials(
                None,
                refresh_token=refresh_token,
                client_id=Config.GOOGLE_CLIENT_ID,
                client_secret=Config.GOOGLE_CLIENT_SECRET,
                token_uri="https://oauth2.googleapis.com/token",
            )
            creds.refresh(GoogleRequest())

            return {
                "access_token": creds.token,
                "expires_at": creds.expiry,
            }
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return None

    @staticmethod
    def create_calendar_event(access_token, summary, start_time, end_time, attendee_emails=None):
        try:
            creds = Credentials(token=access_token)
            service = build("calendar", "v3", credentials=creds)

            event = {
                "summary": summary,
                "start": {"dateTime": start_time.isoformat(), "timeZone": "America/New_York"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "America/New_York"},
                "attendees": [{"email": e} for e in (attendee_emails or [])],
                # Asking Google to auto-generate a Meet link for this event.
                # requestId just needs to be unique per request so Google can
                # dedupe retries - it's not stored or reused anywhere else.
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"meet-{uuid.uuid4()}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            }

            # conferenceDataVersion=1 has to be passed as a request parameter
            # (not inside body) - without it, Google silently ignores
            # conferenceData and no Meet link gets created.
            created_event = service.events().insert(
                calendarId="primary",
                body=event,
                conferenceDataVersion=1,
            ).execute()
            return created_event
        except Exception as e:
            print(f"Failed to create calendar event: {e}")
            return None