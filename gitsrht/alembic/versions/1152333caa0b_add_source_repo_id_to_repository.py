"""Add source_repo_id to Repository

Revision ID: 1152333caa0b
Revises: ddca72f1b7e2
Create Date: 2019-10-14 14:22:16.032157

"""

# revision identifiers, used by Alembic.
revision = '1152333caa0b'
down_revision = 'ddca72f1b7e2'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('repository', sa.Column('source_repo_id',
        sa.Integer, sa.ForeignKey('repository.id')))
    op.add_column('repository', sa.Column('upstream_uri', sa.Unicode))


def downgrade():
    op.drop_column('repository', 'source_repo_id')
    op.drop_column('repository', 'upstream_uri')
