"""Add unique constraint to ACLs

Revision ID: 85ba19185fec
Revises: c167cf8a1271
Create Date: 2020-11-27 10:28:15.303415

"""

# revision identifiers, used by Alembic.
revision = '85ba19185fec'
down_revision = 'c167cf8a1271'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_unique_constraint('uq_access_user_id_repo_id', 'access',
            ['user_id', 'repo_id'])


def downgrade():
    op.drop_constraint('uq_access_user_id_repo_id', 'access')
