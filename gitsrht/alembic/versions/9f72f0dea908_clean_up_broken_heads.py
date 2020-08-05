"""Clean up broken HEADs

Revision ID: 9f72f0dea908
Revises: 3c1285bb23e2
Create Date: 2020-07-28 12:04:39.751225

"""

# revision identifiers, used by Alembic.
revision = '9f72f0dea908'
down_revision = '3c1285bb23e2'

import os.path
import subprocess
from alembic import op
from sqlalchemy.orm import sessionmaker
from pygit2 import GitError, Repository as GitRepository
from gitsrht.types import Repository
from srht.config import cfg
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable):
        yield from iterable

Session = sessionmaker()

post_update = cfg("git.sr.ht", "post-update-script")


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    print("Fixing repositories with broken HEADs")
    for repo in tqdm(session.query(Repository).all()):
        # Sometimes HEAD doesn't exist *at all*,
        # some repositories are also plain uninitialised;
        # git-init(1) says that running it on an existing repository is safe,
        # so do that to try to sort out any unpleasantries
        subprocess.run(["git", "-C", repo.path, "init", "--bare"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "-C", repo.path, "config", "srht.repo-id", str(repo.id)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "-C", repo.path, "config", "receive.denyDeleteCurrent", "ignore"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-f", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "pre-receive")
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-f", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "update")
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-f", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "post-update")
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        git_repo = GitRepository(repo.path)

        try:
            git_repo.lookup_reference("HEAD")
        except GitError:
            # Most likely "corrupted loose reference file: HEAD"
            # This can happen if HEAD is zero-length for some reason,
            # at this point no library solution will work
            # and git(1) will refuse to acknowledge the repository
            with open(os.path.join(repo.path, "HEAD"), "w") as head:
                print("ref: refs/heads/master", file=head)

        # Ensure that dangling HEAD (no default branch) is equivalent to
        # no branches at all; if there are branches but HEAD is dangling,
        # bake in the pre-0.55.0 behaviour of choosing the first branch
        # in iteration order
        if len(list(git_repo.branches.local)) != 0:
            head = git_repo.lookup_reference("HEAD")
            default_branch = git_repo.branches.get(head.target[len("refs/heads/"):])
            if not default_branch:
                branch = list(git_repo.branches.local)[0]
                head.set_target(git_repo.branches[branch].name)


def downgrade():
    pass
