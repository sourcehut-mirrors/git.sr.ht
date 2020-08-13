"""Clean up samples, allow push options

Revision ID: dacab1dcba45
Revises: 9f72f0dea908
Create Date: 2020-08-12 18:45:59.390269

"""

# revision identifiers, used by Alembic.
revision = 'dacab1dcba45'
down_revision = '9f72f0dea908'

import glob
import os.path
from alembic import op
from sqlalchemy.orm import sessionmaker
from pygit2 import Repository as GitRepository
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
    print("Allowing push options, fixing repositories with missing hooks, pruning samples")
    for repo in tqdm(session.query(Repository).all()):
        git_repo = GitRepository(repo.path)
        git_repo.config["receive.advertisePushOptions"] = True

        try:
            # pre-receive wasn't linked for autocreated repositories
            os.symlink(post_update, os.path.join(repo.path, "hooks", "pre-receive"))
        except FileExistsError:
            pass

        try:
            os.unlink(os.path.join(repo.path, "description"))
        except FileNotFoundError:
            pass
        try:
            os.unlink(os.path.join(repo.path, "info", "exclude"))
        except FileNotFoundError:
            pass

        for samp in glob.glob(os.path.join(repo.path, "hooks", "*.sample")):
            os.unlink(samp)


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    for repo in tqdm(session.query(Repository).all()):
        git_repo = GitRepository(repo.path)
        try:
            del git_repo.config["receive.advertisePushOptions"]
        except KeyError:
            pass
