"""Drop oauth_revocation_token

Revision ID: 219060382eff
Revises: 5f3e7771c065
Create Date: 2024-10-31 12:56:00.605405

"""

# revision identifiers, used by Alembic.
revision = '219060382eff'
down_revision = '5f3e7771c065'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    ALTER TABLE "user" DROP COLUMN oauth_revocation_token;
    """)


def downgrade():
    op.execute("""
    ALTER TABLE "user"
    ADD COLUMN oauth_revocation_token character varying(256);
    """)
