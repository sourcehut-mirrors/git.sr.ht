import sqlalchemy as sa
import sqlalchemy_utils as sau
from srht.database import Base

class Webhook(Base):
    __tablename__ = "webhook"
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    description = sa.Column(sa.Unicode(1024))

    oauth_token_id = sa.Column(sa.Integer, sa.ForeignKey("oauthtoken.id"))
    oauth_token = sa.orm.relationship("OAuthToken",
            backref=sa.orm.backref("webhooks"))

    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False)
    user = sa.orm.relationship("User", backref=sa.orm.backref("webhooks"))

    repo_id = sa.Column(sa.Integer, sa.ForeignKey("repository.id"))
    repository = sa.orm.relationship("Repository",
            backref=sa.orm.backref("webhooks"))

    url = sa.Column(sa.Unicode(2048), nullable=False)
    validate_ssl = sa.Column(sa.Boolean, nullable=False, default=True)
