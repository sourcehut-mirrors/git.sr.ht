import hashlib
import os
import pygit2
from flask import Blueprint, redirect, render_template, request, redirect
from flask import abort, url_for
from gitsrht.git import Repository as GitRepository
from gitsrht.repos import delete_artifact, upload_artifact
from gitsrht.types import Artifact
from minio import Minio
from minio.error import BucketAlreadyOwnedByYou, BucketAlreadyExists
from scmsrht.access import check_access, UserAccess
from srht.config import cfg
from srht.database import db
from srht.oauth import loginrequired
from srht.validation import Validation
from werkzeug.utils import secure_filename

artifacts = Blueprint('artifacts', __name__)

# TODO: Make S3 support optional
s3_upstream = cfg("objects", "s3-upstream", default=None)
s3_access_key = cfg("objects", "s3-access-key", default=None)
s3_secret_key = cfg("objects", "s3-secret-key", default=None)
s3_bucket = cfg("git.sr.ht", "s3-bucket", default=None)
s3_prefix = cfg("git.sr.ht", "s3-prefix", default=None)

@artifacts.route("/<owner>/<repo>/refs/<ref>/upload", methods=["POST"])
@loginrequired
def ref_upload(owner, repo, ref):
    owner, repo = check_access(owner, repo, UserAccess.manage)
    with GitRepository(repo.path) as git_repo:
        try:
            tag = git_repo.revparse_single(ref)
        except KeyError:
            abort(404)
        except ValueError:
            abort(404)
        if isinstance(tag, pygit2.Commit):
            target = tag.oid.hex
        else:
            target = tag.target.hex
        valid = Validation(request)
        f = request.files.get("file")
        valid.expect(f, "File is required", field="file")
        if not valid.ok:
            return render_template("ref.html", view="refs",
                    owner=owner, repo=repo, git_repo=git_repo, tag=tag,
                    **valid.kwargs)
        artifact = upload_artifact(valid, repo, target, f, f.filename)
        if not valid.ok:
            return render_template("ref.html", view="refs",
                    owner=owner, repo=repo, git_repo=git_repo, tag=tag,
                    **valid.kwargs)
        db.session.commit()
        return redirect(url_for("repo.ref",
            owner=owner.canonical_name,
            repo=repo.name,
            ref=ref))

@artifacts.route("/<owner>/<repo>/refs/<ref>/<filename>")
def ref_download(owner, repo, ref, filename):
    owner, repo = check_access(owner, repo, UserAccess.read)
    with GitRepository(repo.path) as git_repo:
        try:
            tag = git_repo.revparse_single(ref)
        except KeyError:
            abort(404)
        except ValueError:
            abort(404)
        if isinstance(tag, pygit2.Commit):
            target = tag.oid.hex
        else:
            target = tag.target.hex
    artifact = (Artifact.query
            .filter(Artifact.user_id == owner.id)
            .filter(Artifact.repo_id == repo.id)
            .filter(Artifact.commit == target)
            .filter(Artifact.filename == filename)).one_or_none()
    if not artifact:
        abort(404)
    prefix = os.path.join(s3_prefix, "artifacts",
            repo.owner.canonical_name, repo.name)
    url = f"https://{s3_upstream}/{s3_bucket}/{prefix}/{filename}"
    return redirect(url)

@artifacts.route("/<owner>/<repo>/refs/<ref>/<filename>", methods=["POST"])
def ref_delete(owner, repo, ref, filename):
    owner, repo = check_access(owner, repo, UserAccess.manage)
    with GitRepository(repo.path) as git_repo:
        try:
            tag = git_repo.revparse_single(ref)
        except KeyError:
            abort(404)
        except ValueError:
            abort(404)
        if isinstance(tag, pygit2.Commit):
            target = tag.oid.hex
        else:
            target = tag.target.hex
    artifact = (Artifact.query
            .filter(Artifact.user_id == owner.id)
            .filter(Artifact.repo_id == repo.id)
            .filter(Artifact.commit == target)
            .filter(Artifact.filename == filename)).one_or_none()
    if not artifact:
        abort(404)
    delete_artifact(artifact)
    db.session.commit()
    return redirect(url_for("repo.ref",
        owner=owner.canonical_name, repo=repo.name, ref=ref))
