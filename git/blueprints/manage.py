from flask import Blueprint, request, render_template, redirect
from flask_login import current_user
from srht.config import cfg
from srht.database import db
from srht.validation import Validation
from git.types import Repository, RepoVisibility
from git.decorators import loginrequired
import subprocess
import os
import re

manage = Blueprint('manage', __name__)
repos_path = cfg("cgit", "repos")

@manage.route("/manage")
@loginrequired
def index():
    repos = Repository.query.filter(Repository.owner_id == current_user.id)\
            .order_by(Repository.updated.desc()).all()
    return render_template("manage.html", repos=repos)

@manage.route("/manage/create", methods=["POST"])
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

    if not valid.ok:
        return render_template("manage.html",
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
    db.session.add(repo)

    path = os.path.join(repos_path, "~" + current_user.username)

    subprocess.run(["git", "init", "--bare", repo_name], cwd=path)
    subprocess.run(["ln", "-s", repo_name, repo_name + ".git"], cwd=path)

    # TODO: other shit, probably, like setting up hooks

    db.session.commit()

    return redirect("/~{}/{}".format(current_user.username, repo_name))
