from flask import Blueprint, Response, request, render_template, abort
from flask_login import current_user
import requests
from srht.config import cfg
from gitsrht.types import User, Repository, RepoVisibility

public = Blueprint('cgit', __name__)

upstream = cfg("cgit", "remote")
meta_uri = cfg("network", "meta")

@public.route("/")
def index():
    if current_user:
        repos = Repository.query.filter(Repository.owner_id == current_user.id)\
                .order_by(Repository.updated.desc())\
                .limit(5).all()
    else:
        repos = None
    return render_template("index.html", repos=repos)

@public.route("/~<user>/<repo>", defaults={ "cgit_path": "" })
@public.route("/~<user>/<repo>/", defaults={ "cgit_path": "" })
@public.route("/~<user>/<repo>/<path:cgit_path>")
def cgit_passthrough(user, repo, cgit_path):
    r = requests.get("{}/{}".format(upstream, request.full_path))
    return render_template("cgit.html",
            cgit_html=r.text,
            owner_name="~" + user,
            repo_name=repo)

@public.route("/~<user>/<repo>/patch")
@public.route("/~<user>/<repo>/patch/")
def cgit_plain(user, repo):
    r = requests.get("{}/{}".format(upstream, request.full_path))
    return Response(r.text, mimetype="text/plain")

@public.route("/~<username>")
def user_index(username):
    user = User.query.filter(User.username == username).first()
    if not user:
        abort(404)
    search = request.args.get("search")
    page = request.args.get("page")
    repos = Repository.query\
            .filter(Repository.owner_id == user.id)
    if current_user.id != user.id:
        # TODO: ACLs
        repos = repos.filter(Repository.visibility == RepoVisibility.public)
    if search:
        repos = repos.filter(Repository.name.ilike("%" + search + "%"))
    repos = repos.order_by(Repository.updated.desc())
    total_repos = repos.count()
    total_pages = repos.count() // 5 + 1
    if total_repos % 5 == 0:
        total_pages -= 1
    if page:
        try:
            page = int(page) - 1
            repos = repos.offset(page * 5)
        except:
            page = None
    else:
        page = 0
    repos = repos.limit(5).all()
    r = requests.get(meta_uri + "/api/user/profile", headers={
        "Authorization": "token " + user.oauth_token
    }) # TODO: cache
    if r.status_code == 200:
        profile = r.json()
    else:
        profile = None
    return render_template("user.html",
            user=user,
            repos=repos,
            profile=profile,
            search=search,
            page=page + 1,
            total_pages=total_pages)
