"""Add owner_id_repo_name custom type

Revision ID: 38952f52f32d
Revises: 822baa9910cd
Create Date: 2022-02-16 10:57:33.542300

"""

# revision identifiers, used by Alembic.
revision = '38952f52f32d'
down_revision = '822baa9910cd'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    CREATE TYPE owner_id_repo_name AS (
        owner_id integer,
        repo_name text
    );
    """)


def downgrade():
    op.execute("""
    DROP TYPE owner_id_repo_name;
    """)
