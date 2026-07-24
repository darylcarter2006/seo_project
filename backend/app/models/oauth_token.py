from app.database.db import db
from datetime import datetime


class OAuthToken(db.Model):
    __tablename__ = "oauth_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    access_token = db.Column(db.String(512), nullable=False)
    refresh_token = db.Column(db.String(512), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")

    def is_expired(self):
        expires_at = self.expires_at
        if expires_at.tzinfo is not None:
            return datetime.now(expires_at.tzinfo) >= expires_at
        return datetime.utcnow() >= expires_at

    def __repr__(self):
        return f"<OAuthToken user_id={self.user_id} provider={self.provider}>"