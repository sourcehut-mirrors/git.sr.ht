import os
import sqlalchemy as sa
from sqlalchemy import event
import sqlalchemy_utils as sau
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.dialects import postgresql
from srht.database import Base
from srht.oauth import ExternalUserMixin, ExternalOAuthTokenMixin
from gitsrht.git import Repository as GitRepository
from scmsrht.repos import BaseAccessMixin, BaseRedirectMixin
from scmsrht.repos import RepoVisibility

class User(Base, ExternalUserMixin):
    pass

class OAuthToken(Base, ExternalOAuthTokenMixin):
    pass

class Access(Base, BaseAccessMixin):
    pass

class Redirect(Base, BaseRedirectMixin):
    pass

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
    visibility = sa.Column(
            sau.ChoiceType(RepoVisibility, impl=sa.String()),
            nullable=False,
            default=RepoVisibility.public)
    readme = sa.Column(sa.Unicode)
    clone_status = sa.Column(postgresql.ENUM(
        'NONE', 'IN_PROGRESS', 'COMPLETE', 'ERROR'), nullable=False)
    clone_error = sa.Column(sa.Unicode)

    @declared_attr
    def owner_id(cls):
        return sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)

    @declared_attr
    def owner(cls):
        return sa.orm.relationship('User', backref=sa.orm.backref('repos'))

    def to_dict(self):
        return {
            "id": self.id,
            "created": self.created,
            "updated": self.updated,
            "name": self.name,
            "owner": self.owner.to_dict(short=True),
            "description": self.description,
            "visibility": self.visibility,
        }

    @property
    def git_repo(self):
        if not self._git_repo:
            self._git_repo = GitRepository(self.path)
        return self._git_repo

from gitsrht.types.artifact import Artifact
from gitsrht.types.sshkey import SSHKey
