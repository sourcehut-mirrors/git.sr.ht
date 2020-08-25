"""Add repository.readme

Revision ID: 8fbeb080c434
Revises: d42e577c5dcd
Create Date: 2020-08-22 02:16:15.516120

"""

# revision identifiers, used by Alembic.
revision = '8fbeb080c434'
down_revision = 'd42e577c5dcd'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('repository', sa.Column('readme', sa.Unicode))


def downgrade():
    op.drop_column('repository', 'readme')
