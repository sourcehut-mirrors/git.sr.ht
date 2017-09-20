from flask import Blueprint, request, abort
from gitsrht.types import Repository, RepoVisibility, User
from gitsrht.access import UserAccess, has_access, get_repo
from gitsrht.blueprints.public import check_repo
from gitsrht.repos import create_repo
from srht.validation import Validation
from srht.oauth import oauth
from srht.database import db

api = Blueprint("api", __name__)

repo_json = lambda r: {
    "id": r.id,
    "name": r.name,
    "description": r.description,
    "created": r.created,
    "updated": r.updated,
    "visibility": r.visibility.value
}

@api.route("/api/repos")
@oauth("repos")
def repos_GET(oauth_token):
    start = request.args.get('start') or -1
    repos = Repository.query.filter(Repository.owner_id == oauth_token.user_id)
    if start != -1:
        repos = repos.filter(Repository.id <= start)
    repos = repos.order_by(Repository.id.desc()).limit(11).all()
    if len(repos) != 11:
        next_id = -1
    else:
        next_id = repos[-1].id
        repos = repos[:10]
    return {
        "next": next_id,
        "results": [repo_json(r) for r in repos]
    }

@api.route("/api/repos", methods=["POST"])
@oauth("repos:write")
def repos_POST(oauth_token):
    valid = Validation(request)
    repo = create_repo(valid, oauth_token.user)
    if not valid.ok:
        return valid.response
    return repo_json(repo)

@api.route("/api/repos/~<owner>")
def repos_username_GET(owner):
    user = User.query.filter(User.username == owner).first()
    if not user:
        abort(404)
    start = request.args.get('start') or -1
    repos = (Repository.query
        .filter(Repository.owner_id == user.id)
        .filter(Repository.visibility == RepoVisibility.public)
    )
    if start != -1:
        repos = repos.filter(Repository.id <= start)
    repos = repos.order_by(Repository.id.desc()).limit(11).all()
    if len(repos) != 11:
        next_id = -1
    else:
        next_id = repos[-1].id
        repos = repos[:10]
    return {
        "next": next_id,
        "results": [repo_json(r) for r in repos]
    }

@api.route("/api/repos/~<owner>/<name>")
def repos_by_name_GET(owner, name):
    user, repo = check_repo(owner, name)
    return repo_json(repo)

def prop(valid, resource, prop, **kwargs):
    value = valid.optional(prop, **kwargs)
    if value:
        setattr(resource, prop, value)

@api.route("/api/repos/~<owner>/<name>", methods=["PUT"])
@oauth("repos:write")
def repos_by_name_PUT(oauth_token, owner, name):
    user, repo = check_repo(owner, name, authorized=oauth_token.user)
    valid = Validation(request)
    prop(valid, repo, "visibility", cls=RepoVisibility)
    prop(valid, repo, "description", cls=str)
    db.session.commit()
    return repo_json(repo)
