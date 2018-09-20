from flask import Blueprint, render_template, abort
from flask_login import current_user
from gitsrht.access import get_repo, has_access, UserAccess
from gitsrht.types import User, Repository

repo = Blueprint('repo', __name__)

# TODO: !! SECURITY !!

@repo.route("/<owner>/<repo>")
def summary(owner, repo):
    owner, repo = get_repo(owner, repo)
    if not has_access(repo, UserAccess.read):
        abort(401)
    with open("/home/sircmpwn/sources/wlroots/README.md") as f:
        rm = f.read()
    return render_template("summary.html", owner=owner, repo=repo, rm=rm)
