"""Add unique constraint to artifacts

Revision ID: d42e577c5dcd
Revises: 01412986a44d
Create Date: 2020-08-21 09:17:34.605895

"""

# revision identifiers, used by Alembic.
revision = 'd42e577c5dcd'
down_revision = '01412986a44d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_unique_constraint("repo_artifact_filename_unique",
            "artifacts", ["repo_id", "filename"])


def downgrade():
    op.drop_constraint("repo_artifact_filename_unique", "artifacts", type_="unique")
