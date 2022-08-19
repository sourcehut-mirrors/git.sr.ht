"""Use canonical user ID

Revision ID: 5f3e7771c065
Revises: 08e3d103b672
Create Date: 2022-07-14 12:24:54.356882

"""

# revision identifiers, used by Alembic.
revision = '5f3e7771c065'
down_revision = '08e3d103b672'

from alembic import op
import sqlalchemy as sa


# These tables all have a column referencing "user"(id)
tables = [
    ("access", "user_id"),
    ("artifacts", "user_id"),
    ("gql_user_wh_sub", "user_id"),
    ("oauthtoken", "user_id"),
    ("redirect", "owner_id"),
    ("repo_webhook_subscription", "user_id"),
    ("repository", "owner_id"),
    ("sshkey", "user_id"),
    ("user_webhook_subscription", "user_id"),
]

def upgrade():
    # Drop unique constraints
    op.execute("""
    ALTER TABLE access DROP CONSTRAINT uq_access_user_id_repo_id;
    ALTER TABLE repository DROP CONSTRAINT uq_repo_owner_id_name;
    """)

    # Drop foreign key constraints and update user IDs
    for (table, col) in tables:
        op.execute(f"""
        ALTER TABLE {table} DROP CONSTRAINT {table}_{col}_fkey;
        UPDATE {table} t SET {col} = u.remote_id FROM "user" u WHERE u.id = t.{col};
        """)

    # Update primary key
    op.execute("""
    ALTER TABLE "user" DROP CONSTRAINT user_pkey;
    ALTER TABLE "user" DROP CONSTRAINT user_remote_id_key;
    ALTER TABLE "user" RENAME COLUMN id TO old_id;
    ALTER TABLE "user" RENAME COLUMN remote_id TO id;
    ALTER TABLE "user" ADD PRIMARY KEY (id);
    ALTER TABLE "user" ADD UNIQUE (old_id);
    """)

    # Add foreign key constraints
    for (table, col) in tables:
        op.execute(f"""
        ALTER TABLE {table} ADD CONSTRAINT {table}_{col}_fkey FOREIGN KEY ({col}) REFERENCES "user"(id) ON DELETE CASCADE;
        """)

    # Add unique constraints
    op.execute("""
    ALTER TABLE access ADD CONSTRAINT uq_access_user_id_repo_id UNIQUE (user_id, repo_id);
    ALTER TABLE repository ADD CONSTRAINT uq_repo_owner_id_name UNIQUE (owner_id, name);
    """)


def downgrade():
    # Drop unique constraints
    op.execute("""
    ALTER TABLE access DROP CONSTRAINT uq_access_user_id_repo_id;
    ALTER TABLE repository DROP CONSTRAINT uq_repo_owner_id_name;
    """)

    # Drop foreign key constraints and update user IDs
    for (table, col) in tables:
        op.execute(f"""
        ALTER TABLE {table} DROP CONSTRAINT {table}_{col}_fkey;
        UPDATE {table} t SET {col} = u.old_id FROM "user" u WHERE u.id = t.{col};
        """)

    # Update primary key
    op.execute("""
    ALTER TABLE "user" DROP CONSTRAINT user_pkey;
    ALTER TABLE "user" DROP CONSTRAINT user_old_id_key;
    ALTER TABLE "user" RENAME COLUMN id TO remote_id;
    ALTER TABLE "user" RENAME COLUMN old_id TO id;
    ALTER TABLE "user" ADD PRIMARY KEY (id);
    ALTER TABLE "user" ADD UNIQUE (remote_id);
    """)

    # Add foreign key constraints
    for (table, col) in tables:
        op.execute(f"""
        ALTER TABLE {table} ADD CONSTRAINT {table}_{col}_fkey FOREIGN KEY ({col}) REFERENCES "user"(id) ON DELETE CASCADE;
        """)

    # Add unique constraints
    op.execute("""
    ALTER TABLE access ADD CONSTRAINT uq_access_user_id_repo_id UNIQUE (user_id, repo_id);
    ALTER TABLE repository ADD CONSTRAINT uq_repo_owner_id_name UNIQUE (owner_id, name);
    """)
