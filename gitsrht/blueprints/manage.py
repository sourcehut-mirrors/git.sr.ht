from flask import Blueprint, request, render_template
from flask import redirect, session, url_for
from flask_login import current_user
from srht.config import cfg
from srht.database import db
from srht.validation import Validation
from gitsrht.types import Repository, RepoVisibility, Redirect
from gitsrht.decorators import loginrequired
from gitsrht.access import check_access, UserAccess
from gitsrht.repos import create_repo, rename_repo
import shutil

manage = Blueprint('manage', __name__)
repos_path = cfg("cgit", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

@manage.route("/create")
@loginrequired
def index():
    another = request.args.get("another")
    return render_template("create.html", another=another)

@manage.route("/create", methods=["POST"])
@loginrequired
def create():
    valid = Validation(request)
    repo = create_repo(valid, current_user)
    if not valid.ok:
        return render_template("create.html", **valid.kwargs)
    another = valid.optional("another")
    if another == "on":
        return redirect("/create?another")
    else:
        return redirect("/~{}/{}".format(current_user.username, repo.name))

@manage.route("/<owner_name>/<repo_name>/settings/info")
@loginrequired
def settings_info(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        return redirect(url_for(".settings_info",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_info.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/info", methods=["POST"])
@loginrequired
def settings_info_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        repo = repo.new_repo
    valid = Validation(request)
    desc = valid.optional("description", default=repo.description)
    repo.description = desc
    db.session.commit()
    return redirect("/{}/{}/settings/info".format(owner_name, repo_name))

@manage.route("/<owner_name>/<repo_name>/settings/rename")
@loginrequired
def settings_rename(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        return redirect(url_for(".settings_rename",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_rename.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/rename", methods=["POST"])
@loginrequired
def settings_rename_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        repo = repo.new_repo
    valid = Validation(request)
    repo = rename_repo(owner, repo, valid)
    if not repo:
        return render_template("settings_rename.html", owner=owner, repo=repo,
                **valid.kwargs)
    return redirect("/{}/{}".format(owner_name, repo.name))

@manage.route("/<owner_name>/<repo_name>/settings/access")
@loginrequired
def settings_access(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        return redirect(url_for(".settings_manage",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_access.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/delete")
@loginrequired
def settings_delete(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        return redirect(url_for(".settings_delete",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_delete.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/delete", methods=["POST"])
@loginrequired
def settings_delete_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        repo = repo.new_repo
    shutil.rmtree(repo.path)
    db.session.delete(repo)
    db.session.commit()
    session["notice"] = "{}/{} was deleted.".format(
        owner.canonical_name, repo.name)
    return redirect("/" + owner.canonical_name)
