import sqlalchemy as sa
import sqlalchemy_utils as sau
from git.db import Base

class Repository(Base):
    __tablename__ = 'oauthtoken'
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    owner_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'))
    owner = sa.orm.relationship('User', backref=sa.orm.backref('repos'))
    name = sa.Column(sa.Unicode(256), nullable=False)
