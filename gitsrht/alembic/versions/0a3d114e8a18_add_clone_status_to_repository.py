"""Add clone_status to repository

Revision ID: 0a3d114e8a18
Revises: 163a7732e6a0
Create Date: 2022-02-15 08:25:12.564021

"""

# revision identifiers, used by Alembic.
revision = '0a3d114e8a18'
down_revision = '163a7732e6a0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    CREATE TYPE clone_status AS ENUM (
        'NONE',
        'IN_PROGRESS',
        'COMPLETE',
        'ERROR'
    );

    ALTER TABLE repository
    ADD COLUMN clone_status clone_status NOT NULL DEFAULT 'NONE';
    ALTER TABLE repository
    ALTER COLUMN clone_status DROP DEFAULT;
    ALTER TABLE repository
    ADD COLUMN clone_error varchar
    CHECK ((clone_status = 'ERROR') != (clone_error IS NULL));
    ALTER TABLE repository
    DROP COLUMN clone_in_progress;
    """)


def downgrade():
    op.execute("""
    ALTER TABLE repository
    DROP COLUMN clone_error;
    ALTER TABLE repository
    DROP COLUMN clone_status;
    DROP TYPE clone_status;
    ALTER TABLE repository
    ADD COLUMN clone_in_progress boolean NOT NULL DEFAULT false;
    ALTER TABLE repository
    ALTER COLUMN clone_in_progress DROP DEFAULT;
    """)
