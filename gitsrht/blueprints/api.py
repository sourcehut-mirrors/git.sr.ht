import base64
import json
import pygit2
from flask import Blueprint, current_app, request, send_file, abort
from gitsrht.annotations import validate_annotation
from gitsrht.blueprints.repo import lookup_ref, get_log, collect_refs
from gitsrht.git import Repository as GitRepository, commit_time, annotate_tree
from gitsrht.webhooks import RepoWebhook
from io import BytesIO
from scmsrht.access import UserAccess
from scmsrht.blueprints.api import get_user, get_repo
from scmsrht.redis import redis
from srht.api import paginated_response
from srht.oauth import current_token, oauth
from srht.validation import Validation

data = Blueprint("api.data", __name__)

def commit_to_dict(c):
    return {
        "id": str(c.id),
        "short_id": c.short_id,
        "author": {
            "email": c.author.email,
            "name": c.author.name,
        },
        "committer": {
            "email": c.committer.email,
            "name": c.committer.name,
        },
        "timestamp": commit_time(c),
        "message": c.message,
        "tree": str(c.tree_id),
        "parents": [str(p.id) for p in c.parents],
        "signature": {
            "signature": base64.b64encode(c.gpg_signature[0]).decode(),
            "data": base64.b64encode(c.gpg_signature[1]).decode(),
        } if c.gpg_signature[0] else None
    }

def tree_to_dict(t):
    return {
        "id": str(t.id),
        "short_id": t.short_id,
        "entries": [
            {
                "name": e.name,
                "id": str(e.id),
                "type": e.type,
                "mode": e.filemode,
            } for e in t
        ]
    }

@data.route("/api/repos/<reponame>/refs", defaults={"username": None})
@data.route("/api/<username>/repos/<reponame>/refs")
@oauth("data:read")
def repo_refs_GET(username, reponame):
    user = get_user(username)
    repo = get_repo(user, reponame)

    with GitRepository(repo.path) as git_repo:
        refs = list(git_repo.references)
        # TODO: pagination
        return {
            "next": None,
            "results": [
                {
                    "target": str(git_repo.references[ref].target),
                    "name": ref,
                } for ref in refs
            ],
            "total": len(refs),
            "results_per_page": len(refs),
        }

# dear god, this routing
@data.route("/api/repos/<reponame>/log",
        defaults={"username": None, "ref": None, "path": ""})
@data.route("/api/repos/<reponame>/log/<path:ref>",
        defaults={"username": None, "path": ""})
@data.route("/api/repos/<reponame>/log/<ref>/<path:path>",
        defaults={"username": None})
@data.route("/api/<username>/repos/<reponame>/log",
        defaults={"ref": None, "path": ""})
@data.route("/api/<username>/repos/<reponame>/log/<path:ref>",
        defaults={"path": ""})
@data.route("/api/repos/<username>/<reponame>/log/<ref>/<path:path>")
@oauth("data:read")
def repo_commits_GET(username, reponame, ref, path):
    user = get_user(username)
    repo = get_repo(user, reponame)

    commits_per_page=50
    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return { "next": next_id, "results": [],
                    "total": 0, "results_per_page": commits_per_page }
        commit, ref, path = lookup_ref(git_repo, ref, path)
        start = request.args.get("start")
        if start:
            commit = git_repo.get(start)
        commits = get_log(git_repo, commit, commits_per_page)
        next_id = None
        if len(commits) > commits_per_page:
            next_id = str(commits[-1].id)
        return {
            "next": next_id,
            "results": [commit_to_dict(c) for c in commits],
            # TODO: Track total commits per repo per branch
            "total": -1,
            "results_per_page": commits_per_page
        }

@data.route("/api/repos/<reponame>/tree",
        defaults={"username": None, "ref": None, "path": ""})
@data.route("/api/repos/<reponame>/tree/<path:ref>",
        defaults={"username": None, "path": ""})
@data.route("/api/repos/<reponame>/tree/<ref>/<path:path>",
        defaults={"username": None})
@data.route("/api/<username>/repos/<reponame>/tree",
        defaults={"ref": None, "path": ""})
@data.route("/api/<username>/repos/<reponame>/tree/<path:ref>",
        defaults={"path": ""})
@data.route("/api/<username>/repos/<reponame>/tree/<ref>/<path:path>")
@oauth("data:read")
def repo_tree_GET(username, reponame, ref, path):
    user = get_user(username)
    repo = get_repo(user, reponame)

    with GitRepository(repo.path) as git_repo:
        commit, ref, path = lookup_ref(git_repo, ref, path)
        if isinstance(commit, pygit2.Commit):
            tree = commit.tree
        elif isinstance(commit, pygit2.Tree):
            tree = commit
        else:
            abort(404)

        path = [p for p in path.split("/") if p]
        for part in path:
            if not tree or part not in tree:
                abort(404)
            entry = tree[part]
            if entry.type == "blob":
                abort(404)
            tree = git_repo.get(entry.id)
        if not tree:
            abort(404)
        return tree_to_dict(tree)

@data.route("/api/repos/<reponame>/annotate", methods=["PUT"])
@data.route("/api/<username>/repos/<reponame>/annotate", methods=["PUT"])
@oauth("repo:write")
def repo_annotate_PUT(username, reponame):
    user = get_user(username)
    repo = get_repo(user, reponame, needs=UserAccess.manage)

    valid = Validation(request)

    for oid, annotations in valid.source.items():
        valid.expect(isinstance(oid, str), "blob keys must be strings")
        valid.expect(isinstance(annotations, list),
                "blob values must be lists of annotations")
        if not valid.ok:
            return valid.response
        for anno in annotations:
            validate_annotation(valid, anno)
        if not valid.ok:
            return valid.response
        redis.set(f"git.sr.ht:git:annotations:{repo.id}:{oid}",
                json.dumps(annotations))
        # Invalidate rendered markup cache
        redis.delete(f"git.sr.ht:git:highlight:{oid}")

    return { }, 200

@data.route("/api/repos/<reponame>/blob/<path:ref>",
        defaults={"username": None, "path": ""})
@data.route("/api/repos/<reponame>/blob/<ref>/<path:path>",
        defaults={"username": None})
@data.route("/api/<username>/blob/<reponame>/blob/<path:ref>",
        defaults={"path": ""})
@data.route("/api/<username>/repos/<reponame>/blob/<ref>/<path:path>")
@oauth("data:read")
def repo_blob_GET(username, reponame, ref, path):
    user = get_user(username)
    repo = get_repo(user, reponame)

    with GitRepository(repo.path) as git_repo:
        commit, ref, path = lookup_ref(git_repo, ref, path)
        if not commit:
            abort(404)

        entry = None
        if isinstance(commit, pygit2.Blob):
            blob = commit
        else:
            blob = None
            tree = commit.tree
            path = path.split("/")
            for part in path:
                if part == "":
                    continue
                if part not in tree:
                    abort(404)
                entry = tree[part]
                if entry.type == "blob":
                    tree = annotate_tree(git_repo, tree, commit)
                    commit = next(e.commit for e in tree if e.name == entry.name)
                    blob = git_repo.get(entry.id)
                    break
                tree = git_repo.get(entry.id)
        if not blob:
            abort(404)

        return send_file(BytesIO(blob.data),
                as_attachment=blob.is_binary,
                attachment_filename=entry.name if entry else None,
                mimetype="text/plain" if not blob.is_binary else None)


def _webhook_filters(query, username, reponame):
    user = get_user(username)
    repo = get_repo(user, reponame)
    return query.filter(RepoWebhook.Subscription.repo_id == repo.id)

def _webhook_create(sub, valid, username, reponame):
    user = get_user(username)
    repo = get_repo(user, reponame)
    sub.repo_id = repo.id
    sub.sync = valid.optional("sync", cls=bool, default=False)
    return sub

RepoWebhook.api_routes(data, "/api/<username>/repos/<reponame>",
        filters=_webhook_filters, create=_webhook_create)
