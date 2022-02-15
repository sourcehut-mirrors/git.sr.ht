import os
import sqlalchemy as sa
from sqlalchemy import event
from srht.database import Base
from srht.oauth import ExternalUserMixin, ExternalOAuthTokenMixin
from gitsrht.git import Repository as GitRepository
from scmsrht.repos import BaseAccessMixin, BaseRedirectMixin
from scmsrht.repos import BaseRepositoryMixin, RepoVisibility

class User(Base, ExternalUserMixin):
    pass

class OAuthToken(Base, ExternalOAuthTokenMixin):
    pass

class Access(Base, BaseAccessMixin):
    pass

class Redirect(Base, BaseRedirectMixin):
    pass

class Repository(Base, BaseRepositoryMixin):
    _git_repo = None

    clone_in_progress = sa.Column(sa.Boolean, nullable=False)

    @property
    def git_repo(self):
        if not self._git_repo:
            self._git_repo = GitRepository(self.path)
        return self._git_repo

from gitsrht.types.artifact import Artifact
from gitsrht.types.sshkey import SSHKey
