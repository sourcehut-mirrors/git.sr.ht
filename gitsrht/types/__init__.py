import os
import sqlalchemy as sa
from sqlalchemy import event
import sqlalchemy_utils as sau
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.dialects import postgresql
from srht.database import Base
from srht.oauth import ExternalUserMixin, ExternalOAuthTokenMixin
from gitsrht.git import Repository as GitRepository
from enum import Enum

class User(Base, ExternalUserMixin):
    pass

class OAuthToken(Base, ExternalOAuthTokenMixin):
    pass

class AccessMode(Enum):
    ro = 'ro'
    rw = 'rw'

class Access(Base):
    @declared_attr
    def __tablename__(cls):
        return "access"

    @declared_attr
    def __table_args__(cls):
        return (
            sa.UniqueConstraint('user_id', 'repo_id',
                name="uq_access_user_id_repo_id"),
        )

    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    mode = sa.Column(sau.ChoiceType(AccessMode, impl=sa.String()),
            nullable=False, default=AccessMode.ro)

    @declared_attr
    def user_id(cls):
        return sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)

    @declared_attr
    def user(cls):
        return sa.orm.relationship('User', backref='access_grants')

    @declared_attr
    def repo_id(cls):
        return sa.Column(sa.Integer,
            sa.ForeignKey('repository.id', ondelete="CASCADE"),
            nullable=False)

    @declared_attr
    def repo(cls):
        return  sa.orm.relationship('Repository',
            backref=sa.orm.backref('access_grants', cascade="all, delete"))

    def __repr__(self):
        return '<Access {} {}->{}:{}>'.format(
                self.id, self.user_id, self.repo_id, self.mode)

class Redirect(Base):
    @declared_attr
    def __tablename__(cls):
        return "redirect"

    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    name = sa.Column(sa.Unicode(256), nullable=False)
    path = sa.Column(sa.Unicode(1024))

    @declared_attr
    def owner_id(cls):
        return sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)

    @declared_attr
    def owner(cls):
        return sa.orm.relationship('User')

    @declared_attr
    def new_repo_id(cls):
        return sa.Column(
            sa.Integer,
            sa.ForeignKey('repository.id', ondelete="CASCADE"),
            nullable=False)

    @declared_attr
    def new_repo(cls):
        return sa.orm.relationship('Repository')

class Visibility(Enum):
    # NOTE: SQLAlchemy uses the enum member names, not the values.
    # The values are used by templates. Therfore, we capitalize both.
    PUBLIC = 'PUBLIC'
    PRIVATE = 'PRIVATE'
    UNLISTED = 'UNLISTED'

class Repository(Base):
    @declared_attr
    def __tablename__(cls):
        return "repository"

    @declared_attr
    def __table_args__(cls):
        return (
            sa.UniqueConstraint('owner_id', 'name',
                name="uq_repo_owner_id_name"),
        )

    _git_repo = None
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    name = sa.Column(sa.Unicode(256), nullable=False)
    description = sa.Column(sa.Unicode(1024))
    path = sa.Column(sa.Unicode(1024))
    visibility = sa.Column(postgresql.ENUM(Visibility, name='visibility'), nullable=False)
    readme = sa.Column(sa.Unicode)
    clone_status = sa.Column(postgresql.ENUM(
        'NONE', 'IN_PROGRESS', 'COMPLETE', 'ERROR', name='clone_status'), nullable=False)
    clone_error = sa.Column(sa.Unicode)

    @declared_attr
    def owner_id(cls):
        return sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)

    @declared_attr
    def owner(cls):
        return sa.orm.relationship('User', backref=sa.orm.backref('repos'))

    # This is only used by the REST API
    # TODO: Remove this when the REST API is phased out
    def to_dict(self):
        return {
            "id": self.id,
            "created": self.created,
            "updated": self.updated,
            "name": self.name,
            "owner": self.owner.to_dict(short=True),
            "description": self.description,
            "visibility": self.visibility.value.lower(),
        }

    @property
    def git_repo(self):
        if not self._git_repo:
            self._git_repo = GitRepository(self.path)
        return self._git_repo

from gitsrht.types.artifact import Artifact
