from flask import Blueprint, Response, current_app, request
from scmsrht.access import UserAccess
from scmsrht.repos import RepoVisibility
from scmsrht.types import Access, Repository, User
from gitsrht.blueprints.api import get_user, get_repo
from srht.api import paginated_response
from srht.database import db
from srht.graphql import exec_gql
from srht.oauth import current_token, oauth
from srht.validation import Validation
from sqlalchemy import and_, or_

info = Blueprint("api_info", __name__)

@info.route("/api/repos", defaults={"username": None})
@info.route("/api/<username>/repos")
@oauth("info:read")
def repos_by_user_GET(username):
    user = get_user(username)
    repos = (Repository.query
            .filter(Repository.owner_id == user.id)
            .filter(Repository.visibility != RepoVisibility.autocreated))
    if user.id != current_token.user_id:
        repos = (repos
                .outerjoin(Access._get_current_object(),
                    Access.repo_id == Repository.id)
                .filter(or_(
                    Access.user_id == current_token.user_id,
                    and_(
                        Repository.visibility == RepoVisibility.public,
                        Access.id.is_(None))
                )))
    return paginated_response(Repository.id, repos)

@info.route("/api/repos", methods=["POST"])
@oauth("info:write")
def repos_POST():
    valid = Validation(request)
    user = current_token.user
    resp = current_app.repo_api.create_repo(valid, user)
    if not valid.ok:
        return valid.response
    return resp, 201

@info.route("/api/repos/<reponame>", defaults={"username": None})
@info.route("/api/<username>/repos/<reponame>")
@oauth("info:read")
def repos_by_name_GET(username, reponame):
    user = get_user(username)
    repo = get_repo(user, reponame)
    return repo.to_dict()

@info.route("/api/repos/<reponame>", methods=["PUT"])
@oauth("info:write")
def repos_by_name_PUT(reponame):
    valid = Validation(request)
    user = current_token.user
    repo = get_repo(user, reponame, needs=UserAccess.manage)

    rewrite = lambda value: None if value == "" else value
    input = {
        key: rewrite(valid.source[key]) for key in [
            "name", "description", "visibility",
        ] if valid.source.get(key) is not None
    }

    # Visibility must be uppercase
    if "visibility" in input:
        input["visibility"] = input["visibility"].upper()

    resp = exec_gql(current_app.site, """
        mutation UpdateRepository($id: Int!, $input: RepoInput!) {
            updateRepository(id: $id, input: $input) {
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
    """, user=user, valid=valid, id=repo.id, input=input)

    if not valid.ok:
        return valid.response

    resp = resp["updateRepository"]
    # Convert visibility back to lowercase
    resp["visibility"] = resp["visibility"].lower()
    return resp

@info.route("/api/repos/<reponame>", methods=["DELETE"])
@oauth("info:write")
def repos_by_name_DELETE(reponame):
    user = current_token.user
    repo = get_repo(user, reponame, needs=UserAccess.manage)
    repo_id = repo.id
    current_app.repo_api.delete_repo(repo, user)
    return {}, 204

@info.route("/api/repos/<reponame>/readme", defaults={"username": None})
@info.route("/api/<username>/repos/<reponame>/readme")
@oauth("info:read")
def repos_by_name_readme_GET(username, reponame):
    user = get_user(username)
    repo = get_repo(user, reponame)

    if repo.readme is None:
        return {}, 404
    else:
        return Response(repo.readme, mimetype="text/plain")

@info.route("/api/repos/<reponame>/readme", methods=["PUT"])
@oauth("info:write")
def repos_by_name_readme_PUT(reponame):
    user = current_token.user
    repo = get_repo(user, reponame, needs=UserAccess.manage)

    valid = Validation(request)
    if request.content_type != 'text/html':
        return valid.error("not text/html", field="content-type")

    readme = None
    try:
        readme = request.data.decode("utf-8")
    except:
        return valid.error("README files must be UTF-8 encoded", field="body")

    resp = exec_gql(current_app.site, """
        mutation UpdateRepository($id: Int!, $readme: String!) {
            updateRepository(id: $id, input: {readme: $readme}) { id }
        }
    """, user=user, valid=valid, id=repo.id, readme=readme)

    if not valid.ok:
        return valid.response
    return {}, 204

@info.route("/api/repos/<reponame>/readme", methods=["DELETE"])
@oauth("info:write")
def repos_by_name_readme_DELETE(reponame):
    user = current_token.user
    repo = get_repo(user, reponame, needs=UserAccess.manage)
    valid = Validation(request)
    exec_gql(current_app.site, """
        mutation UpdateRepository($id: Int!) {
            updateRepository(id: $id, input: {readme: null}) { id }
        }
    """, user=user, valid=valid, id=repo.id)
    if not valid.ok:
        return valid.response
    return {}, 204
