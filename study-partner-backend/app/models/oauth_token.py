from app import db
from datetime import datetime


class OAuthToken(db.Model):
    __tablename__ = "oauth_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    access_token = db.Column(db.String(512), nullable=False)
    refresh_token = db.Column(db.String(512), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_expired(self):
        return datetime.utcnow() >= self.expires_at

    def __repr__(self):
        return f"<OAuthToken user_id={self.user_id} provider={self.provider}>"