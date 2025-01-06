"""Add unique constraint to user email

Revision ID: cb6aa17569b3
Revises: 11e216aecb66
Create Date: 2025-01-06 10:41:35.421496

"""

# revision identifiers, used by Alembic.
revision = 'cb6aa17569b3'
down_revision = '11e216aecb66'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    ALTER TABLE "user"
    ADD CONSTRAINT user_email_key
    UNIQUE (email);
    """)


def downgrade():
    op.execute("""
    ALTER TABLE "user"
    DROP CONSTRIANT user_email_key
    """)
