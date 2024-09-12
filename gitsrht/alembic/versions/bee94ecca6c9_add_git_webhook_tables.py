"""Add git webhook tables

Revision ID: bee94ecca6c9
Revises: 5f3e7771c065
Create Date: 2024-08-27 13:13:58.341424

"""

# revision identifiers, used by Alembic.
revision = 'bee94ecca6c9'
down_revision = '5f3e7771c065'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("""
    ALTER TYPE webhook_event ADD VALUE 'GIT_PRE_RECEIVE';
    ALTER TYPE webhook_event ADD VALUE 'GIT_POST_RECEIVE';

    CREATE TABLE gql_git_wh_sub (
        id serial PRIMARY KEY,
        created timestamp without time zone NOT NULL,
        events webhook_event[] NOT NULL,
        url character varying NOT NULL,
        query character varying NOT NULL,
        sync boolean NOT NULL,
        auth_method auth_method NOT NULL,
        token_hash character varying(128),
        grants character varying,
        client_id uuid,
        expires timestamp without time zone,
        node_id character varying,
        user_id integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
        repo_id integer NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
        CONSTRAINT gql_git_wh_sub_auth_method_check
            CHECK ((auth_method = ANY (ARRAY['OAUTH2'::auth_method, 'INTERNAL'::auth_method]))),
        CONSTRAINT gql_git_wh_sub_check
            CHECK (((auth_method = 'OAUTH2'::auth_method) = (token_hash IS NOT NULL))),
        CONSTRAINT gql_git_wh_sub_check1
            CHECK (((auth_method = 'OAUTH2'::auth_method) = (expires IS NOT NULL))),
        CONSTRAINT gql_git_wh_sub_check2
            CHECK (((auth_method = 'INTERNAL'::auth_method) = (node_id IS NOT NULL))),
        CONSTRAINT gql_git_wh_sub_events_check
            CHECK ((array_length(events, 1) > 0))
    );

    CREATE INDEX gql_git_wh_sub_token_hash_idx
        ON gql_git_wh_sub
        USING btree (token_hash);

    CREATE TABLE gql_git_wh_delivery (
        id serial PRIMARY KEY,
        uuid uuid NOT NULL,
        date timestamp without time zone NOT NULL,
        event webhook_event NOT NULL,
        subscription_id integer NOT NULL
            REFERENCES gql_git_wh_sub(id) ON DELETE CASCADE,
        request_body character varying NOT NULL,
        response_body character varying,
        response_headers character varying,
        response_status integer
    );
    """)


def downgrade():
    op.execute("""
    DROP INDEX gql_git_wh_sub_token_hash_idx;
    DROP TABLE gql_git_wh_delivery;
    DROP TABLE gql_git_wh_sub;
    """)
