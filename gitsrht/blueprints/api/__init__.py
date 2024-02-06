import pkg_resources
from flask import abort
from gitsrht.access import UserAccess, get_access
from gitsrht.types import Repository, User
from srht.flask import csrf_bypass
from srht.oauth import current_token, oauth

def get_user(username):
    user = None
    if username == None:
        user = current_token.user
    elif username.startswith("~"):
        user = User.query.filter(User.username == username[1:]).one_or_none()
    if not user:
        abort(404)
    return user

def get_repo(owner, reponame, needs=UserAccess.read):
    repo = (Repository.query
            .filter(Repository.owner_id == owner.id)
            .filter(Repository.name == reponame)).one_or_none()
    if not repo:
        abort(404)
    access = get_access(repo, user=current_token.user)
    if needs not in access:
        abort(403)
    return repo

def register_api(app):
    from gitsrht.blueprints.api.info import info

    app.register_blueprint(info)
    csrf_bypass(info)

    @app.route("/api/version")
    def version():
        try:
            dist = pkg_resources.get_distribution("gitsrht")
            return { "version": dist.version }
        except Exception:
            return { "version": "unknown" }

    @app.route("/api/user/<username>")
    @app.route("/api/user", defaults={"username": None})
    @oauth(None)
    def user_GET(username):
        user = get_user(username)
        return user.to_dict()
