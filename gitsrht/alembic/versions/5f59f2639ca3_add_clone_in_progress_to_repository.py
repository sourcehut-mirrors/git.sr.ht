"""Add clone_in_progress to repository

Revision ID: 5f59f2639ca3
Revises: a4488cc1e42b
Create Date: 2022-02-10 13:24:27.859764

"""

# revision identifiers, used by Alembic.
revision = '5f59f2639ca3'
down_revision = 'a4488cc1e42b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    ALTER TABLE repository
    ADD COLUMN clone_in_progress boolean NOT NULL DEFAULT false;
    ALTER TABLE repository
    ALTER COLUMN clone_in_progress DROP DEFAULT;
    """)


def downgrade():
    op.execute("""
    ALTER TABLE repository
    DROP COLUMN clone_in_progress;
    """)
