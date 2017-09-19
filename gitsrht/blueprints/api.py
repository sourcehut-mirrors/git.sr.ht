from flask import Blueprint, request
from gitsrht.types import Repository, RepoVisibility
from gitsrht.access import UserAccess, has_access, get_repo
from srht.oauth import oauth

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
