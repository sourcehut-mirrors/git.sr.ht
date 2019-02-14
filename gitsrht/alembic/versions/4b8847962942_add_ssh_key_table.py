"""Add ssh key table

Revision ID: 4b8847962942
Revises: 27ad57b7c4a5
Create Date: 2019-02-14 12:04:24.026615

"""

# revision identifiers, used by Alembic.
revision = '4b8847962942'
down_revision = '27ad57b7c4a5'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('sshkey',
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column("meta_id", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("key", sa.String(4096), nullable=False),
        sa.Column("fingerprint", sa.String(512), nullable=False))


def downgrade():
    op.drop_table('sshkey')
