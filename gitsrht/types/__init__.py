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

    def update_visibility(self):
        if not os.path.exists(self.path):
            # Repo dir not initialized yet
            return
        # In order to clone a public repo via http, a git-daemon-export-ok file
        # must exist inside the repo directory. A private repo shouldn't have
        # this file to improve security.
        path = os.path.join(self.path, "git-daemon-export-ok")
        should_exist = self.visibility in (RepoVisibility.public, RepoVisibility.unlisted)
        if should_exist:
            with open(path, 'w'):
                pass
        elif not should_exist and os.path.exists(path):
            os.unlink(path)

    @property
    def git_repo(self):
        if not self._git_repo:
            self._git_repo = GitRepository(self.path)
        return self._git_repo

def update_visibility_event(mapper, connection, target):
    target.update_visibility()

event.listen(Repository, 'after_insert', update_visibility_event)
event.listen(Repository, 'after_update', update_visibility_event)

from gitsrht.types.artifact import Artifact
from gitsrht.types.sshkey import SSHKey
