CREATE TYPE auth_method AS ENUM (
	'OAUTH_LEGACY',
	'OAUTH2',
	'COOKIE',
	'INTERNAL',
	'WEBHOOK'
);

CREATE TYPE clone_status AS ENUM (
	'NONE',
	'IN_PROGRESS',
	'COMPLETE',
	'ERROR'
);

CREATE TYPE visibility AS ENUM (
	'PUBLIC',
	'PRIVATE',
	'UNLISTED'
);

CREATE TYPE webhook_event AS ENUM (
	'REPO_CREATED',
	'REPO_UPDATE',
	'REPO_DELETED',
	'GIT_PRE_RECEIVE',
	'GIT_POST_RECEIVE'
);

CREATE TYPE owner_repo_name AS (
	owner text,
	repo_name text
);

CREATE TYPE owner_id_repo_name AS (
	owner_id integer,
	repo_name text
);

CREATE TABLE "user" (
	id serial PRIMARY KEY,
	username character varying(256) UNIQUE,
	created timestamp without time zone NOT NULL,
	updated timestamp without time zone NOT NULL,
	email character varying(256) NOT NULL,
	user_type character varying NOT NULL DEFAULT 'active_non_paying'::character varying,
	url character varying(256),
	location character varying(256),
	bio character varying(4096),
	suspension_notice character varying(4096),
	-- TODO: Delete these
	oauth_token character varying(256),
	oauth_token_expires timestamp without time zone,
	oauth_token_scopes character varying DEFAULT ''::character varying,
	oauth_revocation_token character varying(256)
);

CREATE INDEX ix_user_username ON "user" USING btree (username);

CREATE TABLE repository (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	updated timestamp without time zone NOT NULL,
	name character varying(256) NOT NULL,
	description character varying(1024),
	owner_id integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
	path character varying(1024),
	visibility visibility NOT NULL,
	readme character varying,
	clone_status clone_status NOT NULL,
	clone_error character varying,
	CONSTRAINT repository_check
		CHECK (((clone_status = 'ERROR'::clone_status) <> (clone_error IS NULL))),
	CONSTRAINT uq_repo_owner_id_name UNIQUE (owner_id, name)
);

CREATE TABLE access (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	updated timestamp without time zone NOT NULL,
	repo_id integer NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
	user_id integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
	mode character varying NOT NULL,
	CONSTRAINT uq_access_user_id_repo_id UNIQUE (user_id, repo_id)
);

CREATE TABLE artifacts (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	user_id integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
	repo_id integer NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
	commit character varying NOT NULL,
	filename character varying NOT NULL,
	checksum character varying NOT NULL,
	size integer NOT NULL,
	CONSTRAINT repo_artifact_filename_unique UNIQUE (repo_id, filename)
);

CREATE TABLE redirect (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	name character varying(256) NOT NULL,
	owner_id integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
	path character varying(1024),
	new_repo_id integer NOT NULL REFERENCES repository(id) ON DELETE CASCADE
);

-- GraphQL webhooks
CREATE TABLE gql_user_wh_sub (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	events webhook_event[] NOT NULL,
	url character varying NOT NULL,
	query character varying NOT NULL,
	auth_method auth_method NOT NULL,
	token_hash character varying(128),
	grants character varying,
	client_id uuid,
	expires timestamp without time zone,
	node_id character varying,
	user_id integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
	CONSTRAINT gql_user_wh_sub_auth_method_check
		CHECK ((auth_method = ANY (ARRAY['OAUTH2'::auth_method, 'INTERNAL'::auth_method]))),
	CONSTRAINT gql_user_wh_sub_check
		CHECK (((auth_method = 'OAUTH2'::auth_method) = (token_hash IS NOT NULL))),
	CONSTRAINT gql_user_wh_sub_check1
		CHECK (((auth_method = 'OAUTH2'::auth_method) = (expires IS NOT NULL))),
	CONSTRAINT gql_user_wh_sub_check2
		CHECK (((auth_method = 'INTERNAL'::auth_method) = (node_id IS NOT NULL))),
	CONSTRAINT gql_user_wh_sub_events_check
		CHECK ((array_length(events, 1) > 0))
);

CREATE INDEX gql_user_wh_sub_token_hash_idx
	ON gql_user_wh_sub
	USING btree (token_hash);

CREATE TABLE gql_user_wh_delivery (
	id serial PRIMARY KEY,
	uuid uuid NOT NULL,
	date timestamp without time zone NOT NULL,
	event webhook_event NOT NULL,
	subscription_id integer NOT NULL
		REFERENCES gql_user_wh_sub(id) ON DELETE CASCADE,
	request_body character varying NOT NULL,
	response_body character varying,
	response_headers character varying,
	response_status integer
);

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

-- Legacy SSH key table, to be fetched from meta.sr.ht instead (TODO: Remove)
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

-- Legacy OAuth (TODO: Remove)
CREATE TABLE oauthtoken (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	updated timestamp without time zone NOT NULL,
	expires timestamp without time zone NOT NULL,
	user_id integer REFERENCES "user"(id) ON DELETE CASCADE,
	token_hash character varying(128) NOT NULL,
	token_partial character varying(8) NOT NULL,
	scopes character varying(512) NOT NULL
);

-- Legacy webhooks (TODO: Remove)
CREATE TABLE user_webhook_subscription (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	url character varying(2048) NOT NULL,
	events character varying NOT NULL,
	user_id integer REFERENCES "user"(id) ON DELETE CASCADE,
	token_id integer REFERENCES oauthtoken(id) ON DELETE CASCADE
);

CREATE TABLE user_webhook_delivery (
	id serial PRIMARY KEY,
	uuid uuid NOT NULL,
	created timestamp without time zone NOT NULL,
	event character varying(256) NOT NULL,
	url character varying(2048) NOT NULL,
	payload character varying(65536) NOT NULL,
	payload_headers character varying(16384) NOT NULL,
	response character varying(65536),
	response_status integer NOT NULL,
	response_headers character varying(16384),
	subscription_id integer NOT NULL
		REFERENCES user_webhook_subscription(id) ON DELETE CASCADE
);

CREATE TABLE repo_webhook_subscription (
	id serial PRIMARY KEY,
	created timestamp without time zone NOT NULL,
	url character varying(2048) NOT NULL,
	events character varying NOT NULL,
	user_id integer REFERENCES "user"(id) ON DELETE CASCADE,
	token_id integer REFERENCES oauthtoken(id) ON DELETE CASCADE,
	repo_id integer REFERENCES repository(id) ON DELETE CASCADE,
	sync boolean DEFAULT false NOT NULL
);

CREATE TABLE repo_webhook_delivery (
	id serial PRIMARY KEY,
	uuid uuid NOT NULL,
	created timestamp without time zone NOT NULL,
	event character varying(256) NOT NULL,
	url character varying(2048) NOT NULL,
	payload character varying(65536) NOT NULL,
	payload_headers character varying(16384) NOT NULL,
	response character varying(65536),
	response_status integer NOT NULL,
	response_headers character varying(16384),
	subscription_id integer NOT NULL
		REFERENCES repo_webhook_subscription(id) ON DELETE CASCADE
);
