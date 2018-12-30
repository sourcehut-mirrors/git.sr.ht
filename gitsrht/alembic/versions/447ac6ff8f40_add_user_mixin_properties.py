"""Add user mixin properties

Revision ID: 447ac6ff8f40
Revises: f86f4bd632a4
Create Date: 2018-12-29 20:42:10.821748

"""

# revision identifiers, used by Alembic.
revision = '447ac6ff8f40'
down_revision = 'f86f4bd632a4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("user", sa.Column("url", sa.String(256)))
    op.add_column("user", sa.Column("location", sa.Unicode(256)))
    op.add_column("user", sa.Column("bio", sa.Unicode(4096)))


def downgrade():
    op.delete_column("user", "url")
    op.delete_column("user", "location")
    op.delete_column("user", "bio")
