"""Add redirect table

Revision ID: f81294e9c2cf
Revises: daf28fd9e001
Create Date: 2017-11-12 14:41:59.099778

"""

# revision identifiers, used by Alembic.
revision = 'f81294e9c2cf'
down_revision = 'daf28fd9e001'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('redirect',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('created', sa.DateTime, nullable=False),
        sa.Column('name', sa.Unicode(256), nullable=False),
        sa.Column('owner_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column('path', sa.Unicode(1024)),
        sa.Column('new_repo_id', 
                sa.Integer,
                sa.ForeignKey('repository.id'),
                nullable=False))

def downgrade():
    op.drop_table('redirect')
