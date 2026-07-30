"""
app/services/persistence.py

Raw database read/write operations, kept separate from scoring/ranking
logic so that logic can be unit-tested with plain Python objects and
no database at all (see tests/test_scoring.py).
"""

from app.database.db import db
from app.models import User, Course, Availability, Preference, Match, MatchProposal


# --- Match persistence ---

def save_match(user_a_id, user_b_id, score, status="pending"):
    match = Match(user_a_id=user_a_id, user_b_id=user_b_id, score=score, status=status)
    db.session.add(match)
    db.session.commit()
    return match


def get_matches(user_id=None, status=None):
    query = Match.query
    if status:
        query = query.filter_by(status=status)
    if user_id:
        query = query.filter(
            (Match.user_a_id == user_id) | (Match.user_b_id == user_id)
        )
    return query.all()


def get_match(match_id):
    return db.session.get(Match, match_id)


def delete_match(match_id):
    """Returns True if a row was deleted, False if not found."""
    match = db.session.get(Match, match_id)
    if not match:
        return False
    db.session.delete(match)
    db.session.commit()
    return True


def update_match_status(match_id, status):
    match = db.session.get(Match, match_id)
    if not match:
        return None
    match.status = status
    db.session.commit()
    return match


def save_match_proposal(match_id, start_time, end_time, topic=None, notion_parent_page_id=None):
    proposal = MatchProposal(
        match_id=match_id,
        start_time=start_time,
        end_time=end_time,
        topic=topic,
        notion_parent_page_id=notion_parent_page_id,
    )
    db.session.add(proposal)
    db.session.commit()
    return proposal


def get_match_proposal(match_id):
    return MatchProposal.query.filter_by(match_id=match_id).first()


# --- User / supporting persistence ---

def create_user(name, email):
    user = User(name=name, email=email)
    db.session.add(user)
    db.session.commit()
    return user


def get_user(user_id):
    return db.session.get(User, user_id)


def get_user_by_email(email):
    return User.query.filter_by(email=email).first()


def email_domain(email):
    """Returns the part after '@', lowercased -- used as a lightweight
    proxy for "school" since there's no dedicated school field on User.
    See README for the tradeoffs of this approach."""
    return email.rsplit("@", 1)[-1].lower()


def get_all_users():
    return User.query.all()


def add_availability(user_id, day_of_week, start_hour, end_hour):
    slot = Availability(
        user_id=user_id, day_of_week=day_of_week, start_hour=start_hour, end_hour=end_hour
    )
    db.session.add(slot)
    db.session.commit()
    return slot


def clear_availability(user_id):
    """Deletes all of a user's existing Availability rows -- used when
    re-saving a profile, so re-submitting the form replaces the schedule
    instead of accumulating duplicate/stale rows alongside it."""
    Availability.query.filter_by(user_id=user_id).delete()
    db.session.commit()


def set_preference(user_id, study_style, pace):
    pref = Preference.query.filter_by(user_id=user_id).first()
    if pref:
        pref.study_style = study_style
        pref.pace = pace
    else:
        pref = Preference(user_id=user_id, study_style=study_style, pace=pace)
        db.session.add(pref)
    db.session.commit()
    return pref


def get_or_create_course(code, name):
    course = Course.query.filter_by(code=code).first()
    if not course:
        course = Course(code=code, name=name)
        db.session.add(course)
        db.session.commit()
    return course


def enroll_user_in_course(user, course):
    if course not in user.courses:
        user.courses.append(course)
        db.session.commit()
    return user
