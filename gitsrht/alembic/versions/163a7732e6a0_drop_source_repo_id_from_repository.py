"""Drop source_repo_id from repository

Revision ID: 163a7732e6a0
Revises: 5f59f2639ca3
Create Date: 2022-02-14 09:59:52.962377

"""

# revision identifiers, used by Alembic.
revision = '163a7732e6a0'
down_revision = '5f59f2639ca3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    ALTER TABLE repository
    DROP COLUMN upstream_uri;
    ALTER TABLE repository
    DROP COLUMN source_repo_id;
    """)


def downgrade():
    op.execute("""
    ALTER TABLE repository
    ADD COLUMN upstream_uri varchar;
    ALTER TABLE repository
    ADD COLUMN source_repo_id integer;
    """)
