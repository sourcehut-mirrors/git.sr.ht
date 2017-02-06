from flask import Blueprint, Response, request, render_template
import requests
from srht.config import cfg
from git.types import User, Repository, RepoVisibility

public = Blueprint('cgit', __name__)

upstream = cfg("cgit", "remote")
meta_uri = cfg("network", "meta")

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
    repos = Repository.query\
            .filter(Repository.owner_id == user.id)\
            .filter(Repository.visibility == RepoVisibility.public)
    if search:
        repos = repos.filter(Repository.name.ilike("%" + search + "%"))
    repos = repos.order_by(Repository.updated.desc()).all()
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
            search=search)
