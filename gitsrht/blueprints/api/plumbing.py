import base64
import binascii
import pygit2
from flask import Blueprint, Response, abort, request
from gitsrht.git import Repository as GitRepository
from scmsrht.blueprints.api import get_user, get_repo
from srht.oauth import oauth

plumbing = Blueprint("api_plumbing", __name__)

def libgit2_object_type_to_str(otype):
    return {
        pygit2.GIT_OBJ_COMMIT: "commit",
        pygit2.GIT_OBJ_TREE: "tree",
        pygit2.GIT_OBJ_BLOB: "blob",
        pygit2.GIT_OBJ_TAG: "tag",
    }[otype]

@plumbing.route("/api/repos/<reponame>/odb/<oid>", defaults={"username": None})
@plumbing.route("/api/<username>/repos/<reponame>/odb/<oid>")
@oauth("data:read")
def repo_get_object(username, reponame, oid):
    user = get_user(username)
    repo = get_repo(user, reponame)
    with GitRepository(repo.path) as git_repo:
        try:
            otype, odata = git_repo.odb.read(oid)
        except KeyError:
            return "object not found", 404
        return Response(odata, headers={
            "X-Git-Object-Type": libgit2_object_type_to_str(otype),
        }, content_type="application/octet-stream")

@plumbing.route("/api/repos/<reponame>/lookup/<oid_prefix>",
        defaults={"username": None})
@plumbing.route("/api/<username>/repos/<reponame>/lookup/<oid_prefix>")
@oauth("data:read")
def repo_lookup_prefix(username, reponame, oid_prefix):
    user = get_user(username)
    repo = get_repo(user, reponame)
    with GitRepository(repo.path) as git_repo:
        # XXX: This will look up anything, not just a partially qualified Oid
        try:
            o = git_repo.revparse_single(oid_prefix)
        except KeyError:
            return "object not found", 404
        except ValueError:
            return "ambiguous oid", 409
        return o.oid.hex

@plumbing.route("/api/repos/<reponame>/refdb/<path:refname>",
        defaults={"username": None})
@plumbing.route("/api/<username>/repos/<reponame>/refdb/<path:refname>")
@oauth("data:read")
def repo_get_ref(username, reponame, refname):
    user = get_user(username)
    repo = get_repo(user, reponame)
    with GitRepository(repo.path) as git_repo:
        try:
            ref = git_repo.lookup_reference(refname)
        except pygit2.InvalidSpecError:
            return "invalid reference", 400
        except KeyError:
            return "unknown reference", 404
        if isinstance(ref.target, pygit2.Oid):
            # direct reference
            return f"{ref.target.hex} {ref.peel().oid.hex}"
        else:
            # symbolic reference
            return str(ref.target)
