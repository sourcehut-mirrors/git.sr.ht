from flask import Blueprint
from flask_login import current_user
from gitsrht.types import User, Repository

repo = Blueprint('repo', __name__)

# TODO: !! SECURITY !!

@repo.route("/<owner>/<name>")
def summary(owner, name):
    return "hi!"
