"""
This blueprint is used internally by gitsrht-shell to speed up git pushes, by
taking advantage of the database connection already established by the web app.
"""

import base64
from flask import Blueprint, request
from srht.config import get_origin
from scmsrht.access import has_access, UserAccess
from scmsrht.urls import get_clone_urls
from gitsrht.repos import GitRepoApi
from gitsrht.types import User, Repository, RepoVisibility, Redirect
from srht.crypto import verify_request_signature
from srht.database import db
from srht.flask import csrf_bypass
from srht.validation import Validation

internal = Blueprint("internal", __name__)

@csrf_bypass
@internal.route("/internal/push-check", methods=["POST"])
def push_check():
    verify_request_signature(request)
    valid = Validation(request)
    path = valid.require("path")
    user_id = valid.require("user_id", cls=int)
    access = valid.require("access", cls=int)
    if not valid.ok:
        return valid.response
    access = UserAccess(access)
    user = User.query.filter(User.id == user_id).one()

    repo = Repository.query.filter(Repository.path == path).first()
    if not repo:
        redir = Redirect.query.filter(Redirect.path == path).first()
        if redir:
            origin = get_origin("git.sr.ht", external=True)
            repo = redir.new_repo
            # TODO: orgs
            return {
                "redirect": 'git@{origin}:{repo.owner.username}/{repo.name}'
            }, 302

        # Autocreate this repo
        _path, repo_name = os.path.split(path)
        owner = os.path.basename(_path)
        if "~" + user.username != owner:
            return { }, 401

        valid = Validation({ "name": repo_name })
        repo_api = GitRepoApi()
        repo = repo_api.create_repo(valid, user)
        if not valid.ok:
            sys.exit(128)
        repo.visibility = RepoVisibility.autocreated
        db.session.commit()
        return { }, 200

    if not has_access(repo, access, user):
        return { }, 401

    return { }, 200
