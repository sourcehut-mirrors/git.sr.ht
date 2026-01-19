-- +brant Up
CREATE TABLE sshkey (
	id serial PRIMARY KEY,
	rid uuid NOT NULL UNIQUE DEFAULT gen_uuidv7(),
	created timestamp without time zone,
	repo_id integer REFERENCES repository(id) ON DELETE CASCADE,
	key character varying(4096) NOT NULL,
	key_type character varying(256) NOT NULL,
	fingerprint_sha256 character varying(512) NOT NULL,
	comment character varying(256),
	access access_mode NOT NULL,
	last_used timestamp without time zone
);

ALTER TABLE sshkey
	ADD CONSTRAINT sshkey_repo_id_fingerprint_sha256_key
	UNIQUE (repo_id, fingerprint_sha256);

-- +brant Down
DROP TABLE sshkey;
