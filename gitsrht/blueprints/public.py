from flask import Blueprint, Response, request, render_template, abort, stream_with_context
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

def check_repo(user, repo):
    u = User.query.filter(User.username == user).first()
    if not u:
        abort(404)
    _repo = Repository.query.filter(Repository.owner_id == u.id)\
            .filter(Repository.name == repo).first()
    if not _repo:
        abort(404)
    if _repo.visibility == RepoVisibility.private:
        if not current_user or current_user.id != _repo.owner_id:
            abort(404)
    return _repo

@public.route("/~<user>/<repo>", defaults={ "cgit_path": "" })
@public.route("/~<user>/<repo>/", defaults={ "cgit_path": "" })
@public.route("/~<user>/<repo>/<path:cgit_path>")
def cgit_passthrough(user, repo, cgit_path):
    check_repo(user, repo)
    r = requests.get("{}/{}".format(upstream, request.full_path))
    if r.status_code != 200:
        abort(r.status_code)
    base = cfg("network", "git").replace("http://", "").replace("https://", "")
    clone_urls = [
        ("ssh://git@{}/~{}/{}", "git@{}/~{}/{}"),
        ("https://{}/~{}/{}",),
        ("git://{}/~{}/{}",)
    ]
    if "Repository seems to be empty" in r.text:
        clone_urls = clone_urls[:2]
    clone_text = "<tr><td colspan='3'>" +\
        "<a rel='vcs-git' href='__CLONE_URL__' title='~{}/{} Git repository'>__CLONE_URL__</a>".format(user, repo) +\
        "</td></tr>"
    if not clone_text in r.text:
        clone_text = clone_text.replace(" colspan='3'", "")
    text = r.text.replace(
        clone_text,
        " ".join(["<tr><td colspan='3'><a href='{}'>{}</a></td></tr>".format(
            url[0].format(base, user, repo), url[-1].format(base, user, repo))
            for url in clone_urls])
    )
    if "Repository seems to be empty" in r.text:
        text = text.replace("<th class='left'>Clone</th>", "<th class='left'>Push</th>")
    return render_template("cgit.html",
            cgit_html=text,
            owner_name="~" + user,
            repo_name=repo)

@public.route("/~<user>/<repo>/snapshot/<tarball>.tar.xz")
@public.route("/~<user>/<repo>/plain/<tarball>.tar.xz")
def tarball(user, repo, tarball):
    check_repo(user, repo)
    r = requests.get("{}/{}".format(upstream, request.full_path), stream=True)
    return Response(stream_with_context(r.iter_content()), content_type=r.headers['content-type'])

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
    if not current_user or current_user.id != user.id:
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
