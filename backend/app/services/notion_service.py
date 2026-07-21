"""
app/services/notion_service.py
--------------------------------
Handles OAuth + shared study-notes page creation against the Notion API.
Simpler than GoogleCalendarService/MSGraphService because Notion access
tokens don't expire, so there's no refresh_access_token() here.

Docs:
  - OAuth: https://developers.notion.com/docs/authorization
  - Pages: https://developers.notion.com/reference/post-page
"""

import base64
from urllib.parse import urlencode

import requests

from app.config import Config


class NotionService:

    AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.notion.com/v1/oauth/token"
    API_BASE_URL = "https://api.notion.com/v1"

    @staticmethod
    def _get_basic_auth_header():
        """Notion's token exchange authenticates with Basic auth (base64
        client_id:client_secret) instead of putting the secret in the body."""
        credentials = f"{Config.NOTION_CLIENT_ID}:{Config.NOTION_CLIENT_SECRET}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @staticmethod
    def _api_headers(access_token):
        """Every Notion API call (not just OAuth) needs Notion-Version pinned,
        or the API may respond with a shape this code doesn't expect."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": Config.NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

    @staticmethod
    def get_authorization_url():
        """Builds the Notion "connect an integration" URL the browser gets redirected to."""
        params = {
            "client_id": Config.NOTION_CLIENT_ID,
            "response_type": "code",
            "owner": "user",
            "redirect_uri": Config.NOTION_REDIRECT_URI,
        }
        return f"{NotionService.AUTH_URL}?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_tokens(code):
        """
        Trades the one-time code from the callback for an access token.
        Notion tokens don't expire and there's no refresh_token, so the
        return shape is intentionally smaller than Google's/Microsoft's.
        """
        headers = {
            "Authorization": NotionService._get_basic_auth_header(),
            "Content-Type": "application/json",
        }
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": Config.NOTION_REDIRECT_URI,
        }
        response = requests.post(NotionService.TOKEN_URL, headers=headers, json=body)
        response.raise_for_status()
        token_data = response.json()

        return {
            "access_token": token_data["access_token"],
            # Notion also returns "workspace_id" / "workspace_name" / "bot_id"
            # here if we ever need to show the user which workspace they
            # connected - not needed for token storage today.
        }

    @staticmethod
    def create_shared_page(access_token, parent_page_id, topic, student_a_name, student_b_name):
        """
        Creates a new Notion page under `parent_page_id` as a shared study
        notes page for a confirmed match. `parent_page_id` has to be a page
        the user shared with this integration when they connected it -
        Notion doesn't allow creating a page with no parent.

        Returns the created page dict (page["url"] is the shareable link),
        or None on failure.
        """
        headers = NotionService._api_headers(access_token)
        body = {
            "parent": {"page_id": parent_page_id},
            "properties": {
                "title": [
                    {"text": {"content": f"Study Session: {topic}"}}
                ]
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": f"Shared notes for {student_a_name} & {student_b_name}."
                                }
                            }
                        ]
                    },
                }
            ],
        }

        try:
            response = requests.post(
                f"{NotionService.API_BASE_URL}/pages",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to create Notion page: {e}")
            return None
