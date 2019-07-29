"""Fix cascades on webhook tables

Revision ID: ddca72f1b7e2
Revises: 61b01f874da8
Create Date: 2019-07-29 11:57:14.486544

"""

# revision identifiers, used by Alembic.
revision = 'ddca72f1b7e2'
down_revision = '61b01f874da8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_constraint(
            constraint_name="repo_webhook_delivery_subscription_id_fkey",
            table_name="repo_webhook_delivery",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_delivery_subscription_id_fkey",
            source_table="repo_webhook_delivery",
            referent_table="repo_webhook_subscription",
            local_cols=["subscription_id"],
            remote_cols=["id"],
            ondelete="CASCADE")
    op.drop_constraint(
            constraint_name="user_webhook_delivery_subscription_id_fkey",
            table_name="user_webhook_delivery",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="user_webhook_delivery_subscription_id_fkey",
            source_table="user_webhook_delivery",
            referent_table="user_webhook_subscription",
            local_cols=["subscription_id"],
            remote_cols=["id"],
            ondelete="CASCADE")

def downgrade():
    op.drop_constraint(
            constraint_name="repo_webhook_delivery_subscription_id_fkey",
            table_name="repo_webhook_delivery",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="repo_webhook_delivery_subscription_id_fkey",
            source_table="repo_webhook_delivery",
            referent_table="repo_webhook_subscription",
            local_cols=["subscription_id"],
            remote_cols=["id"])
    op.drop_constraint(
            constraint_name="user_webhook_delivery_subscription_id_fkey",
            table_name="user_webhook_delivery",
            type_="foreignkey")
    op.create_foreign_key(
            constraint_name="user_webhook_delivery_subscription_id_fkey",
            source_table="user_webhook_delivery",
            referent_table="user_webhook_subscription",
            local_cols=["subscription_id"],
            remote_cols=["id"])
