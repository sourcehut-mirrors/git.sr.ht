"""Add visibility enum

Revision ID: 64fcd80183c8
Revises: 38952f52f32d
Create Date: 2022-02-24 12:29:23.314019

"""

# revision identifiers, used by Alembic.
revision = '64fcd80183c8'
down_revision = '38952f52f32d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    UPDATE repository SET visibility = 'private' WHERE visibility = 'autocreated';

    CREATE TYPE visibility AS ENUM (
        'PUBLIC',
        'PRIVATE',
        'UNLISTED'
    );

    ALTER TABLE repository
    ALTER COLUMN visibility TYPE visibility USING upper(visibility)::visibility;
    """)


def downgrade():
    op.execute("""
    ALTER TABLE repository
    ALTER COLUMN visibility TYPE varchar USING lower(visibility::varchar);
    DROP TYPE visibility;
    """)
