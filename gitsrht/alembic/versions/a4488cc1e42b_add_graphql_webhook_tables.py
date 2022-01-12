"""Add GraphQL webhook tables

Revision ID: a4488cc1e42b
Revises: 85ba19185fec
Create Date: 2022-01-11 10:02:40.806122

"""

# revision identifiers, used by Alembic.
revision = 'a4488cc1e42b'
down_revision = '85ba19185fec'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    CREATE TYPE webhook_event AS ENUM (
        'REPO_CREATED',
        'REPO_UPDATE',
        'REPO_DELETED'
    );

    CREATE TYPE auth_method AS ENUM (
        'OAUTH_LEGACY',
        'OAUTH2',
        'COOKIE',
        'INTERNAL',
        'WEBHOOK'
    );

    CREATE TABLE gql_user_wh_sub (
        id serial PRIMARY KEY,
        created timestamp NOT NULL,
        events webhook_event[] NOT NULL check (array_length(events, 1) > 0),
        url varchar NOT NULL,
        query varchar NOT NULL,

        auth_method auth_method NOT NULL check (auth_method in ('OAUTH2', 'INTERNAL')),
        token_hash varchar(128) check ((auth_method = 'OAUTH2') = (token_hash IS NOT NULL)),
        grants varchar,
        client_id uuid,
        expires timestamp check ((auth_method = 'OAUTH2') = (expires IS NOT NULL)),
        node_id varchar check ((auth_method = 'INTERNAL') = (node_id IS NOT NULL)),

        user_id integer NOT NULL references "user"(id)
    );

    CREATE INDEX gql_user_wh_sub_token_hash_idx ON gql_user_wh_sub (token_hash);

    CREATE TABLE gql_user_wh_delivery (
        id serial PRIMARY KEY,
        uuid uuid NOT NULL,
        date timestamp NOT NULL,
        event webhook_event NOT NULL,
        subscription_id integer NOT NULL references gql_user_wh_sub(id) ON DELETE CASCADE,
        request_body varchar NOT NULL,
        response_body varchar,
        response_headers varchar,
        response_status integer
    );
    """)


def downgrade():
    op.execute("""
    DROP TABLE gql_user_wh_delivery;
    DROP INDEX gql_user_wh_sub_token_hash_idx;
    DROP TABLE gql_user_wh_sub;
    DROP TYPE auth_method;
    DROP TYPE webhook_event;
    """)
