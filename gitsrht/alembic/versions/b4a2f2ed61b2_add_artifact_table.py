"""Add artifact table

Revision ID: b4a2f2ed61b2
Revises: 1152333caa0b
Create Date: 2020-02-14 12:00:52.658629

"""

# revision identifiers, used by Alembic.
revision = 'b4a2f2ed61b2'
down_revision = '1152333caa0b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table("artifacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created", sa.DateTime, nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey('repository.id'), nullable=False),
        sa.Column("commit", sa.Unicode, nullable=False),
        sa.Column("filename", sa.Unicode, nullable=False),
        sa.Column("checksum", sa.Unicode, nullable=False),
        sa.Column("size", sa.Integer, nullable=False))

def downgrade():
    op.drop_table("artifacts")
