"""Remove obsolete webhook table

Revision ID: 27ad57b7c4a5
Revises: 447ac6ff8f40
Create Date: 2018-12-31 13:31:13.665300

"""

# revision identifiers, used by Alembic.
revision = '27ad57b7c4a5'
down_revision = '447ac6ff8f40'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_table("webhook")


def downgrade():
    op.create_table('webhook',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('created', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
        sa.Column('updated', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
        sa.Column('description', sa.VARCHAR(length=1024), autoincrement=False, nullable=True),
        sa.Column('oauth_token_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('repo_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('url', sa.VARCHAR(length=2048), autoincrement=False, nullable=False),
        sa.Column('validate_ssl', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['oauth_token_id'], ['oauthtoken.id'], name='webhook_oauth_token_id_fkey'),
        sa.ForeignKeyConstraint(['repo_id'], ['repository.id'], name='webhook_repo_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='webhook_user_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='webhook_pkey'))
