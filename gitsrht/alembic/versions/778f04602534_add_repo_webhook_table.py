"""Add repo webhook table

Revision ID: 778f04602534
Revises: 69b1f39fdca7
Create Date: 2019-04-19 11:41:54.626104

"""

# revision identifiers, used by Alembic.
revision = '778f04602534'
down_revision = '69b1f39fdca7'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils as sau


def upgrade():
    op.create_table('repo_webhook_subscription',
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created", sa.DateTime, nullable=False),
        sa.Column("url", sa.Unicode(2048), nullable=False),
        sa.Column("events", sa.Unicode, nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id")),
        sa.Column("token_id", sa.Integer, sa.ForeignKey("oauthtoken.id")),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repository.id")),
    )
    op.create_table('repo_webhook_delivery',
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uuid", sau.UUIDType, nullable=False),
        sa.Column("created", sa.DateTime, nullable=False),
        sa.Column("event", sa.Unicode(256), nullable=False),
        sa.Column("url", sa.Unicode(2048), nullable=False),
        sa.Column("payload", sa.Unicode(65536), nullable=False),
        sa.Column("payload_headers", sa.Unicode(16384), nullable=False),
        sa.Column("response", sa.Unicode(65536)),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("response_headers", sa.Unicode(16384)),
        sa.Column("subscription_id", sa.Integer,
            sa.ForeignKey('repo_webhook_subscription.id'), nullable=False),
    )


def downgrade():
    op.drop_table('repo_webhook_delivery')
    op.drop_table('repo_webhook_subscription')
