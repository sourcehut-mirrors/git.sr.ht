"""Add cascades for repo deletion

Revision ID: 8d26b98e7d44
Revises: ce3a03ec34a5
Create Date: 2018-07-11 07:15:41.973647

"""

# revision identifiers, used by Alembic.
revision = '8d26b98e7d44'
down_revision = 'ce3a03ec34a5'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_constraint(
            constraint_name="redirect_new_repo_id_fkey",
            table_name="redirect",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="redirect_new_repo_id_fkey",
            source_table="redirect",
            referent_table="repository",
            local_cols=["new_repo_id"],
            remote_cols=["id"],
            ondelete="CASCADE")
    op.drop_constraint(
            constraint_name="access_repo_id_fkey",
            table_name="access",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="access_repo_id_fkey",
            source_table="access",
            referent_table="repository",
            local_cols=["repo_id"],
            remote_cols=["id"],
            ondelete="CASCADE")
    op.drop_constraint(
            constraint_name="webhook_repo_id_fkey",
            table_name="webhook",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="webhook_repo_id_fkey",
            source_table="webhook",
            referent_table="repository",
            local_cols=["repo_id"],
            remote_cols=["id"],
            ondelete="CASCADE")
    op.drop_constraint(
            constraint_name="webhook_oauth_token_id_fkey",
            table_name="webhook",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="webhook_oauth_token_id_fkey",
            source_table="webhook",
            referent_table="oauthtoken",
            local_cols=["oauth_token_id"],
            remote_cols=["id"],
            ondelete="CASCADE")


def downgrade():
    op.drop_constraint(
            constraint_name="redirect_new_repo_id_fkey",
            table_name="redirect",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="redirect_new_repo_id_fkey",
            source_table="redirect",
            referent_table="repository",
            local_cols=["new_repo_id"],
            remote_cols=["id"])
    op.drop_constraint(
            constraint_name="access_repo_id_fkey",
            table_name="access",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="access_repo_id_fkey",
            source_table="access",
            referent_table="repository",
            local_cols=["repo_id"],
            remote_cols=["id"])
    op.drop_constraint(
            constraint_name="webhook_repo_id_fkey",
            table_name="webhook",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="webhook_repo_id_fkey",
            source_table="webhook",
            referent_table="repository",
            local_cols=["repo_id"],
            remote_cols=["id"])
