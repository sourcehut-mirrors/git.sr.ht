from flask import Blueprint, current_app, request
from flask import render_template, abort
from srht.config import cfg
from srht.flask import paginate_query
from srht.oauth import current_user
from srht.search import search_by
from gitsrht.types import Access, Repository, User, RepoVisibility
from sqlalchemy import and_, or_

public = Blueprint('public', __name__)

@public.route("/")
def index():
    if current_user:
        repos = (Repository.query
                .filter(Repository.owner_id == current_user.id)
                .order_by(Repository.updated.desc())
                .limit(10)).all()
        return render_template("dashboard.html", repos=repos)
    return render_template("index.html")

@public.route("/~<username>")
@public.route("/~<username>/")
def user_index(username):
    user = User.query.filter(User.username == username).first()
    if not user:
        abort(404)
    terms = request.args.get("search")
    repos = (Repository.query
            .filter(Repository.owner_id == user.id))
    if current_user and current_user.id != user.id:
        repos = (repos
                .outerjoin(Access,
                    Access.repo_id == Repository.id)
                .filter(or_(
                    Access.user_id == current_user.id,
                    Repository.visibility == RepoVisibility.PUBLIC,
                )))
    elif not current_user:
        repos = repos.filter(Repository.visibility == RepoVisibility.PUBLIC)

    search_error = None
    try:
        repos = search_by(repos, terms,
                [Repository.name, Repository.description])
    except ValueError as ex:
        search_error = str(ex)

    repos = repos.order_by(Repository.updated.desc())
    repos, pagination = paginate_query(repos)

    return render_template("user.html",
            user=user, repos=repos,
            search=terms, search_error=search_error, **pagination)
