from flask import Blueprint, request, render_template, redirect
from flask_login import current_user
from srht.config import cfg
from srht.database import db
from srht.validation import Validation
from gitsrht.types import Repository, RepoVisibility
from gitsrht.decorators import loginrequired
from gitsrht.access import get_repo, has_access, UserAccess
import shutil
import subprocess
import os
import re

manage = Blueprint('manage', __name__)
repos_path = cfg("cgit", "repos")

@manage.route("/create")
@loginrequired
def index():
    another = request.args.get("another")
    return render_template("create.html", another=another)

@manage.route("/create", methods=["POST"])
@loginrequired
def create():
    valid = Validation(request)
    repo_name = valid.require("repo-name", friendly_name="Name")
    valid.expect(not repo_name or re.match(r'^[a-z._-][a-z0-9._-]*$', repo_name),
            "Name must match [a-z._-][a-z0-9._-]*", field="repo-name")
    description = valid.optional("repo-description")
    visibility = valid.require("repo-visibility", friendly_name="Visibility")
    valid.expect(not visibility or visibility in [m[0] for m in RepoVisibility.__members__.items()],
            "Expected one of public, private, unlisted for visibility", field="repo-visibility")
    repos = Repository.query.filter(Repository.owner_id == current_user.id)\
            .order_by(Repository.updated.desc()).all()
    valid.expect(not repo_name or not repo_name in [r.name for r in repos],
            "This name is already in use.", field="repo-name")
    another = valid.optional("another")

    if not valid.ok:
        return render_template("create.html",
                valid=valid,
                repos=repos,
                repo_name=repo_name,
                repo_description=description,
                visibility=visibility)

    repo = Repository()
    repo.name = repo_name
    repo.description = description
    repo.owner_id = current_user.id
    repo.visibility = RepoVisibility[visibility]
    repo.path = os.path.join(repos_path, "~" + current_user.username, repo.name)
    db.session.add(repo)

    subprocess.run(["mkdir", "-p", repo.path])
    subprocess.run(["git", "init", "--bare"], cwd=repo.path)

    db.session.commit()

    subprocess.run(["git", "config", "srht.repo-id", str(repo.id)], cwd=repo.path)
    hook_src = os.path.join(os.path.dirname(__file__), "..", "hooks", "update")
    shutil.copy(hook_src, os.path.join(repo.path, "hooks", "update"))

    if another == "on":
        return redirect("/create?another")
    else:
        return redirect("/~{}/{}".format(current_user.username, repo_name))

@manage.route("/<owner_name>/<repo_name>/settings/info")
def settings_info(owner_name, repo_name):
    owner, repo = get_repo(owner_name, repo_name)
    if not has_access(repo, UserAccess.read):
        abort(404)
    if not has_access(repo, UserAccess.manage):
        abort(403)
    return render_template("settings_info.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/info", methods=["POST"])
def settings_info_POST(owner_name, repo_name):
    owner, repo = get_repo(owner_name, repo_name)
    if not has_access(repo, UserAccess.read):
        abort(404)
    if not has_access(repo, UserAccess.manage):
        abort(403)
    valid = Validation(request)
    desc = valid.optional("description", default=repo.description)
    repo.description = desc
    db.session.commit()
    return redirect("/{}/{}/settings/info".format(owner_name, repo_name))
