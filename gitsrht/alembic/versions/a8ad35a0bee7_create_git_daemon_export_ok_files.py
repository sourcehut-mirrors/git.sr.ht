"""Create git-daemon-export-ok files

Revision ID: a8ad35a0bee7
Revises: b4a2f2ed61b2
Create Date: 2020-04-11 00:48:04.430870

"""

# revision identifiers, used by Alembic.
revision = 'a8ad35a0bee7'
down_revision = 'b4a2f2ed61b2'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from gitsrht.types import Repository
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable):
        yield from iterable


Session = sessionmaker()


def upgrade():
    print("/!\ WARNING: Not creating git-daemon-export-ok files")


def downgrade():
    pass
