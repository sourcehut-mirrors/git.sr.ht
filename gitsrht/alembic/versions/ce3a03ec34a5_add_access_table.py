"""Add access table

Revision ID: ce3a03ec34a5
Revises: f81294e9c2cf
Create Date: 2018-01-27 11:17:49.944381

"""

# revision identifiers, used by Alembic.
revision = 'ce3a03ec34a5'
down_revision = 'f81294e9c2cf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('access',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('created', sa.DateTime, nullable=False),
        sa.Column('updated', sa.DateTime, nullable=False),
        sa.Column('repo_id', sa.Integer, sa.ForeignKey('repository.id'), nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column('mode', sa.String(), nullable=False, default='ro'))


def downgrade():
    op.drop_table('access')
