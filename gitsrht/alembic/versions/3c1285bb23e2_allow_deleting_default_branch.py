"""Allow deleting default branch

Revision ID: 3c1285bb23e2
Revises: 163fc2d2a2ea
Create Date: 2020-07-28 12:04:39.751225

"""

# revision identifiers, used by Alembic.
revision = '3c1285bb23e2'
down_revision = '163fc2d2a2ea'

import subprocess
from alembic import op
from sqlalchemy.orm import sessionmaker
from gitsrht.types import Repository
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable):
        yield from iterable

Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    print("Setting receive.denyDeleteCurrent=ignore")
    for repo in tqdm(session.query(Repository).all()):
        subprocess.run(["git", "config", "receive.denyDeleteCurrent", "ignore"],
            cwd=repo.path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    for repo in tqdm(session.query(Repository).all()):
        subprocess.run(["git", "config", "--unset", "receive.denyDeleteCurrent"],
            cwd=repo.path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
