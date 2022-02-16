"""Add owner_repo_name custom type

Revision ID: 822baa9910cd
Revises: 0a3d114e8a18
Create Date: 2022-02-16 10:06:54.271103

"""

# revision identifiers, used by Alembic.
revision = '822baa9910cd'
down_revision = '0a3d114e8a18'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    CREATE TYPE owner_repo_name AS (
        owner text,
        repo_name text
    );
    """)


def downgrade():
    op.execute("""
    DROP TYPE owner_repo_name;
    """)
