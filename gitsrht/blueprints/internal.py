"""
This blueprint is used internally by gitsrht-shell to speed up git pushes, by
taking advantage of the database connection already established by the web app.
"""

from datetime import datetime
from flask import Blueprint, request
from gitsrht.repos import GitRepoApi
from gitsrht.types import User, Repository, RepoVisibility, Redirect
from scmsrht.access import has_access, UserAccess
from scmsrht.urls import get_clone_urls
from srht.config import cfg, get_origin
from srht.crypto import verify_request_signature
from srht.database import db
from srht.flask import csrf_bypass
from srht.oauth import UserType
from srht.validation import Validation
import base64
import os

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

    def push_context(user, repo):
        if access == UserAccess.write:
            repo.updated = datetime.utcnow()
            db.session.commit()
        return {
            "user": user.to_dict(),
            "repo": {
                "path": repo.path,
                **repo.to_dict(),
            },
        }

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

        if access == UserAccess.write:
            # Autocreate this repo
            _path, repo_name = os.path.split(path)
            owner = os.path.basename(_path)
            if "~" + user.username != owner:
                return { }, 401

            valid = Validation({ "name": repo_name })
            repo_api = GitRepoApi()
            repo = repo_api.create_repo(valid, user)
            if not valid.ok:
                return valid.response
            repo.visibility = RepoVisibility.autocreated
            db.session.commit()
            return push_context(user, repo), 200
        else:
            return { }, 404

    if not has_access(repo, access, user):
        return { }, 401

    if access == UserAccess.write and user.user_type == UserType.suspended:
        return {
            "why": "Your account has been suspended with the following notice:\n" +
                user.suspension_notice + "\n" +
                "Please contact support: " + cfg("sr.ht", "owner-email"),
        }, 401

    return push_context(user, repo), 200
