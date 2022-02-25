import hashlib
import os.path
import pygit2
import re
import shutil
import subprocess
from gitsrht.types import Artifact, Repository, Redirect
from minio import Minio
from srht.config import cfg
from srht.database import db
from srht.graphql import exec_gql, GraphQLError
from werkzeug.utils import secure_filename

repos_path = cfg("git.sr.ht", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

s3_upstream = cfg("objects", "s3-upstream", default=None)
s3_access_key = cfg("objects", "s3-access-key", default=None)
s3_secret_key = cfg("objects", "s3-secret-key", default=None)
s3_bucket = cfg("git.sr.ht", "s3-bucket", default=None)
s3_prefix = cfg("git.sr.ht", "s3-prefix", default=None)

object_storage_enabled = all([
    s3_upstream,
    s3_access_key,
    s3_secret_key,
    s3_bucket,
])

def delete_artifact(artifact):
    minio = Minio(s3_upstream, access_key=s3_access_key,
            secret_key=s3_secret_key, secure=True)
    repo = artifact.repo
    prefix = os.path.join(s3_prefix, "artifacts",
            repo.owner.canonical_name, repo.name)
    try:
        minio.remove_object(s3_bucket, f"{prefix}/{artifact.filename}")
    except ResponseError as err:
        print(err)
    db.session.delete(artifact)

def upload_artifact(valid, repo, commit, f, filename):
    fn = secure_filename(filename)
    artifact = (Artifact.query
            .filter(Artifact.user_id == repo.owner_id)
            .filter(Artifact.repo_id == repo.id)
            .filter(Artifact.filename == fn)).one_or_none()
    valid.expect(not artifact, "A file by this name was already uploaded.",
            field="file")
    if not valid.ok:
        return None
    minio = Minio(s3_upstream, access_key=s3_access_key,
            secret_key=s3_secret_key, secure=True)
    prefix = os.path.join(s3_prefix, "artifacts",
            repo.owner.canonical_name, repo.name)
    try:
        minio.make_bucket(s3_bucket)
    except:
        # Thanks for not giving us more specific exceptions, minio
        pass
    sha = hashlib.sha256()
    buf = f.read(1024)
    while len(buf) > 0:
        sha.update(buf)
        buf = f.read(1024)
    size = f.tell()
    f.seek(0)
    minio.put_object(s3_bucket, f"{prefix}/{fn}", f, size,
            content_type="application/octet-stream")
    artifact = Artifact()
    artifact.user_id = repo.owner_id
    artifact.repo_id = repo.id
    artifact.commit = commit
    artifact.filename = fn
    artifact.checksum = f"sha256:{sha.hexdigest()}"
    artifact.size = size
    db.session.add(artifact)
    return artifact

def get_repo_path(owner, repo_name):
    return os.path.join(repos_path, "~" + owner.username, repo_name)

def create_repo(valid, user=None):
    repo_name = valid.require("name", friendly_name="Name")
    description = valid.optional("description")
    visibility = valid.optional("visibility")
    if not valid.ok:
        return None

    # Convert the visibility to uppercase. This is needed for the REST API
    # TODO: Remove this when the REST API is phased out
    if visibility is not None:
        visibility = visibility.upper()

    resp = exec_gql("git.sr.ht", """
        mutation CreateRepository(
                $name: String!,
                $visibility: Visibility = PUBLIC,
                $description: String) {
            createRepository(
                    name: $name,
                    visibility: $visibility,
                    description: $description) {
                id
                created
                updated
                name
                owner {
                    canonicalName
                    ... on User {
                        name: username
                    }
                }
                description
                visibility
            }
        }
    """, valid=valid, user=user, name=repo_name,
        description=description, visibility=visibility)

    if not valid.ok:
        return None
    return resp["createRepository"]

def clone_repo(valid):
    cloneUrl = valid.require("cloneUrl", friendly_name="Clone URL")
    name = valid.require("name", friendly_name="Name")
    description = valid.optional("description")
    visibility = valid.optional("visibility")
    if not valid.ok:
        return None

    resp = exec_gql("git.sr.ht", """
        mutation CreateRepository(
                $name: String!,
                $visibility: Visibility = UNLISTED,
                $description: String,
                $cloneUrl: String) {
            createRepository(name: $name,
                    visibility: $visibility,
                    description: $description,
                    cloneUrl: $cloneUrl) {
                name
            }
        }
    """, valid=valid, name=name, visibility=visibility,
        description=description, cloneUrl=cloneUrl)

    if not valid.ok:
        return None
    return resp["createRepository"]

def delete_repo(repo, user=None):
    exec_gql("git.sr.ht", """
        mutation DeleteRepository($id: Int!) {
            deleteRepository(id: $id) { id }
        }
    """, user=user, id=repo.id)
