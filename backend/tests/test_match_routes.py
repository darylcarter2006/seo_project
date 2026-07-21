import unittest
from unittest.mock import patch

from app import create_app, db


class TestConfirmMatchRoute(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def _valid_payload(self):
        return {
            "user_id": 1,
            "partner_id": 2,
            "student_a": {"course_id": 101, "availability": {"monday": [("14:00", "16:00")]}},
            "student_b": {"course_id": 101, "availability": {"monday": [("14:00", "16:00")]}},
            "start_time": "2026-07-22T14:00:00",
            "end_time": "2026-07-22T15:00:00",
        }

    @staticmethod
    def _token_for_provider(google_token=None, notion_token=None):
        """get_valid_access_token is called once per provider in the route,
        so a single flat return_value can't tell Google and Notion apart -
        this builds a side_effect that answers based on the provider kwarg."""
        def side_effect(user_id, provider="google_calendar"):
            if provider == "google_calendar":
                return google_token
            if provider == "notion":
                return notion_token
            return None
        return side_effect

    # Patched where the names are *used* (match_routes), not where they're
    # defined - patching the original module wouldn't affect the reference
    # match_routes already imported.
    @patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
    @patch("app.routes.match_routes.get_valid_access_token")
    def test_successful_confirmation_books_calendar(self, mock_get_token, mock_create_event):
        mock_get_token.side_effect = self._token_for_provider(google_token="fake-access-token")
        mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}

        response = self.client.post("/api/match/confirm", json=self._valid_payload())

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["calendar_status"], "booked")
        self.assertEqual(body["meet_link"], "https://meet.google.com/abc-defg-hij")
        self.assertEqual(body["notion_status"], "not connected")  # no notion token in this test

    @patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
    @patch("app.routes.match_routes.get_valid_access_token")
    def test_calendar_failure_falls_back_gracefully(self, mock_get_token, mock_create_event):
        mock_get_token.side_effect = self._token_for_provider(google_token="fake-access-token")
        mock_create_event.return_value = None  # simulates a Calendar API failure

        response = self.client.post("/api/match/confirm", json=self._valid_payload())

        self.assertEqual(response.status_code, 200)  # match is still confirmed
        body = response.get_json()
        self.assertEqual(body["calendar_status"], "pending calendar confirmation")
        self.assertNotIn("meet_link", body)

    def test_invalid_match_returns_400(self):
        payload = self._valid_payload()
        payload["student_b"]["course_id"] = 999  # different course -> score 0.0

        response = self.client.post("/api/match/confirm", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    @patch("app.routes.match_routes.NotionService.create_shared_page")
    @patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
    @patch("app.routes.match_routes.get_valid_access_token")
    def test_notion_page_created_when_connected(
        self, mock_get_token, mock_create_event, mock_create_page
    ):
        mock_get_token.side_effect = self._token_for_provider(
            google_token="fake-google-token", notion_token="fake-notion-token"
        )
        mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
        mock_create_page.return_value = {"url": "https://notion.so/study-session-abc123"}

        payload = self._valid_payload()
        payload["notion_parent_page_id"] = "some-parent-page-id"
        payload["topic"] = "Calc II"
        payload["student_a_name"] = "Alice"
        payload["student_b_name"] = "Bob"

        response = self.client.post("/api/match/confirm", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["notion_status"], "created")
        self.assertEqual(body["notes_page_url"], "https://notion.so/study-session-abc123")
        mock_create_page.assert_called_once()

    @patch("app.routes.match_routes.NotionService.create_shared_page")
    @patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
    @patch("app.routes.match_routes.get_valid_access_token")
    def test_notion_failure_does_not_block_match_confirmation(
        self, mock_get_token, mock_create_event, mock_create_page
    ):
        mock_get_token.side_effect = self._token_for_provider(
            google_token="fake-google-token", notion_token="fake-notion-token"
        )
        mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
        mock_create_page.return_value = None  # simulates a Notion API failure

        payload = self._valid_payload()
        payload["notion_parent_page_id"] = "some-parent-page-id"

        response = self.client.post("/api/match/confirm", json=payload)

        self.assertEqual(response.status_code, 200)  # match still confirmed
        body = response.get_json()
        self.assertEqual(body["notion_status"], "pending notion confirmation")
        self.assertNotIn("notes_page_url", body)


if __name__ == "__main__":
    unittest.main()
