from flask import Blueprint, request
from flask import render_template, abort
from flask_login import current_user
import requests
from srht.config import cfg
from srht.flask import paginate_query
from gitsrht.types import User, Repository, RepoVisibility
from sqlalchemy import or_

public = Blueprint('public', __name__)

meta_uri = cfg("meta.sr.ht", "origin")

@public.route("/")
def index():
    if current_user:
        repos = (Repository.query
                .filter(Repository.owner_id == current_user.id)
                .filter(Repository.visibility != RepoVisibility.autocreated)
                .order_by(Repository.updated.desc())
                .limit(10)).all()
    else:
        repos = None
    return render_template("index.html", repos=repos)

@public.route("/~<username>")
@public.route("/~<username>/")
def user_index(username):
    user = User.query.filter(User.username == username).first()
    if not user:
        abort(404)
    search = request.args.get("search")
    repos = Repository.query\
            .filter(Repository.owner_id == user.id)
    if not current_user or current_user.id != user.id:
        # TODO: ACLs
        repos = repos.filter(Repository.visibility == RepoVisibility.public)
    if search:
        repos = repos.filter(or_(
                Repository.name.ilike("%" + search + "%"),
                Repository.description.ilike("%" + search + "%")))
    repos = repos.order_by(Repository.updated.desc())
    repos, pagination = paginate_query(repos)

    r = requests.get(meta_uri + "/api/user/profile", headers={
        "Authorization": "token " + user.oauth_token
    }) # TODO: cache
    if r.status_code == 200:
        profile = r.json()
    else:
        profile = None

    return render_template("user.html",
            user=user, repos=repos, profile=profile,
            search=search, **pagination)
