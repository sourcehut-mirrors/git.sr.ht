"""Add unique constraint to repos

Revision ID: 163fc2d2a2ea
Revises: a8ad35a0bee7
Create Date: 2020-07-23 14:13:45.279463

"""

# revision identifiers, used by Alembic.
revision = '163fc2d2a2ea'
down_revision = 'a8ad35a0bee7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_unique_constraint('uq_repo_owner_id_name', 'repository',
            ['owner_id', 'name'])


def downgrade():
    op.drop_constraint('uq_repo_owner_id_name', 'repository')
