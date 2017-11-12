from flask import Blueprint, request, redirect, abort, url_for
from gitsrht.types import Repository, RepoVisibility, User, Webhook, Redirect
from gitsrht.access import UserAccess, has_access, get_repo
from gitsrht.blueprints.public import check_repo
from gitsrht.repos import create_repo
from srht.validation import Validation, valid_url
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

wh_json = lambda wh: {
    "id": wh.id,
    "created": wh.created,
    "description": wh.description,
    "url": wh.url,
    "validate_ssl": wh.validate_ssl,
    "repo": "~{}/{}".format(wh.repository.owner.username,
        wh.repository.name) if wh.repository else None
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
    if isinstance(repo, Redirect):
        return redirect(url_for(".repos_by_name_GET",
            owner=owner, name=repo.new_repo.name))
    return repo_json(repo)

def prop(valid, resource, prop, **kwargs):
    value = valid.optional(prop, **kwargs)
    if value:
        setattr(resource, prop, value)

@api.route("/api/repos/~<owner>/<name>", methods=["PUT"])
@oauth("repos:write")
def repos_by_name_PUT(oauth_token, owner, name):
    user, repo = check_repo(owner, name, authorized=oauth_token.user)
    if isinstance(repo, Redirect):
        abort(404)
    valid = Validation(request)
    prop(valid, repo, "visibility", cls=RepoVisibility)
    prop(valid, repo, "description", cls=str)
    db.session.commit()
    return repo_json(repo)

@api.route("/api/webhooks")
@oauth("webhooks")
def webhooks_GET(oauth_token):
    start = request.args.get('start') or -1
    webhooks = (Webhook.query
        .filter(Webhook.user_id == oauth_token.user_id)
        .filter(Webhook.repo_id == None)
    )
    if start != -1:
        webhooks = webhooks.filter(Webhook.id <= start)
    webhooks = webhooks.order_by(Webhook.id.desc()).limit(11).all()
    if len(webhooks) != 11:
        next_id = -1
    else:
        next_id = webhooks[-1].id
        webhooks = webhooks[:10]
    return {
        "next": next_id,
        "results": [wh_json(wh) for wh in webhooks]
    }

@api.route("/api/webhooks", methods=["POST"])
@oauth("webhooks:write")
def webhooks_POST(oauth_token):
    valid = Validation(request)
    desc = valid.optional("description", cls=str)
    url = valid.require("url")
    valid.expect(not url or valid_url(url), "This URL is invalid", field="url")
    validate_ssl = valid.optional("validate_ssl", cls=bool, default=True)
    repo = valid.optional("repo", cls=str)
    if repo:
        [owner, name] = repo.split("/")
        if owner.starswith("~"):
            owner = owner[1:]
        # TODO: don't abort here
        _, repo = check_repo(owner, name, authorized=oauth_token.user)
    if not valid.ok:
        return valid.response
    wh = Webhook()
    wh.description = desc
    wh.url = url
    wh.validate_ssl = validate_ssl
    wh.user_id = oauth_token.user_id
    wh.repo_id = repo.id if repo else None
    wh.oauth_token_id = oauth_token.id
    db.session.add(wh)
    db.session.commit()
    return wh_json(wh)
