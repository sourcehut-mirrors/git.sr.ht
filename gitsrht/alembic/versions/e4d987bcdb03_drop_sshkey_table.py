"""Drop sshkey table

Revision ID: e4d987bcdb03
Revises: cb6aa17569b3
Create Date: 2025-01-20 15:14:13.918279

"""

# revision identifiers, used by Alembic.
revision = 'e4d987bcdb03'
down_revision = 'cb6aa17569b3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("DROP TABLE sshkey;")

def downgrade():
    op.execute("""
    CREATE TABLE sshkey (
    	id serial PRIMARY KEY,
    	user_id integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    	meta_id integer NOT NULL,
    	key character varying(4096) NOT NULL,
    	fingerprint character varying(512) NOT NULL
    );
    CREATE INDEX ix_sshkey_key
    	ON sshkey
    	USING btree (md5((key)::text));
    CREATE UNIQUE INDEX ix_sshkey_meta_id
    	ON sshkey
    	USING btree (meta_id);
    """)
