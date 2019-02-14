"""Add index to SSH keys

Revision ID: 69b1f39fdca7
Revises: 4b8847962942
Create Date: 2019-02-14 15:32:35.948396

"""

# revision identifiers, used by Alembic.
revision = '69b1f39fdca7'
down_revision = '4b8847962942'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('ix_sshkey_key', 'sshkey', ['key'])


def downgrade():
    op.drop_index('ix_sshkey_key', 'sshkey')
