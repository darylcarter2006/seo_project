"""
app/models/__init__.py
Re-exports every model so the rest of the app can do:
    from app.models import User, Course, Availability, Preference, Match, OAuthToken
instead of reaching into individual files. Also ensures every model is
registered with SQLAlchemy's metadata before db.create_all() runs.
"""

from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.models.course import Course, user_courses
from app.models.availability import Availability
from app.models.preference import Preference
from app.models.match import Match

__all__ = [
    "OAuthToken",
    "User",
    "Course",
    "user_courses",
    "Availability",
    "Preference",
    "Match",
]
