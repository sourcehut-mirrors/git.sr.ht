import sqlalchemy as sa
import sqlalchemy_utils as sau
from srht.database import Base
from enum import Enum

class RepoVisibility(Enum):
    public = 'public'
    private = 'private'
    unlisted = 'unlisted'

class Repository(Base):
    __tablename__ = 'repository'
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    name = sa.Column(sa.Unicode(256), nullable=False)
    description = sa.Column(sa.Unicode(1024))
    owner_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)
    owner = sa.orm.relationship('User', backref=sa.orm.backref('repos'))
    path = sa.Column(sa.Unicode(1024))
    visibility = sa.Column(
            sau.ChoiceType(RepoVisibility, impl=sa.String()),
            nullable=False,
            default=RepoVisibility.public)
