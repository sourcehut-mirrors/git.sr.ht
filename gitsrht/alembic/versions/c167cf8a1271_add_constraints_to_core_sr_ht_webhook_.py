"""Add constraints to core.sr.ht webhook tables

Revision ID: c167cf8a1271
Revises: 8fbeb080c434
Create Date: 2020-09-07 13:33:55.440129

"""

# revision identifiers, used by Alembic.
revision = 'c167cf8a1271'
down_revision = '8fbeb080c434'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_constraint(
            constraint_name="repo_webhook_subscription_repo_id_fkey",
            table_name="repo_webhook_subscription",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_subscription_repo_id_fkey",
            source_table="repo_webhook_subscription",
            referent_table="repository",
            local_cols=["repo_id"],
            remote_cols=["id"],
            ondelete="CASCADE")
    op.drop_constraint(
            constraint_name="repo_webhook_subscription_token_id_fkey",
            table_name="repo_webhook_subscription",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_subscription_token_id_fkey",
            source_table="repo_webhook_subscription",
            referent_table="oauthtoken",
            local_cols=["token_id"],
            remote_cols=["id"],
            ondelete="CASCADE")
    op.drop_constraint(
            constraint_name="repo_webhook_subscription_user_id_fkey",
            table_name="repo_webhook_subscription",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_subscription_user_id_fkey",
            source_table="repo_webhook_subscription",
            referent_table="user",
            local_cols=["user_id"],
            remote_cols=["id"],
            ondelete="CASCADE")


def downgrade():
    op.drop_constraint(
            constraint_name="repo_webhook_subscription_repo_id_fkey",
            table_name="repo_webhook_subscription",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_subscription_repo_id_fkey",
            source_table="repo_webhook_subscription",
            referent_table="repository",
            local_cols=["repo_id"],
            remote_cols=["id"])
    op.drop_constraint(
            constraint_name="repo_webhook_subscription_token_id_fkey",
            table_name="repo_webhook_subscription",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_subscription_token_id_fkey",
            source_table="repo_webhook_subscription",
            referent_table="oauthtoken",
            local_cols=["token_id"],
            remote_cols=["id"])
    op.drop_constraint(
            constraint_name="repo_webhook_subscription_user_id_fkey",
            table_name="repo_webhook_subscription",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_subscription_user_id_fkey",
            source_table="repo_webhook_subscription",
            referent_table="user",
            local_cols=["user_id"],
            remote_cols=["id"])
