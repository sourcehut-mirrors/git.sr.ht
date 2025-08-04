import contextlib
import hashlib
import os.path
import pygit2
import re
import shutil
import subprocess
from gitsrht.types import Artifact, Repository, Redirect
from minio import Minio
from minio.error import S3Error
from srht.config import cfg
from srht.database import db
from werkzeug.utils import secure_filename

repos_path = cfg("git.sr.ht", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

s3_upstream = cfg("objects", "s3-upstream", default=None)
s3_access_key = cfg("objects", "s3-access-key", default=None)
s3_secret_key = cfg("objects", "s3-secret-key", default=None)
s3_secure = cfg("objects", "s3-insecure", default="no") != "yes"
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
            secret_key=s3_secret_key, secure=s3_secure)
    repo = artifact.repo
    prefix = os.path.join(s3_prefix, "artifacts",
            repo.owner.canonical_name, repo.name)
    try:
        minio.remove_object(s3_bucket, f"{prefix}/{artifact.filename}")
    except S3Error as err:
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
            secret_key=s3_secret_key, secure=s3_secure)
    prefix = os.path.join(s3_prefix, "artifacts",
            repo.owner.canonical_name, repo.name)
    with contextlib.suppress(S3Error):
        minio.make_bucket(s3_bucket)
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
