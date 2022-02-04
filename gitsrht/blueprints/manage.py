import pygit2
from flask import Blueprint, current_app, request, render_template, abort
from flask import redirect, url_for
from gitsrht.git import Repository as GitRepository
from srht.config import cfg
from srht.database import db
from srht.flask import session
from srht.graphql import exec_gql, GraphQLError
from srht.oauth import current_user, loginrequired, UserType
from srht.validation import Validation
from scmsrht.access import check_access, UserAccess
from scmsrht.repos.access import AccessMode
from scmsrht.repos.redirect import BaseRedirectMixin
from scmsrht.repos.repository import RepoVisibility
from scmsrht.types import Access, User
import shutil
import os

manage = Blueprint('manage', __name__)

@manage.route("/create")
@loginrequired
def create_GET():
    another = request.args.get("another")
    name = request.args.get("name")
    return render_template("create.html", another=another, name=name)

@manage.route("/create", methods=["POST"])
@loginrequired
def create_POST():
    if not current_app.repo_api:
        abort(501)
    valid = Validation(request)
    resp = current_app.repo_api.create_repo(valid)
    if not valid.ok:
        return render_template("create.html", **valid.kwargs)

    another = valid.optional("another")
    if another == "on":
        return redirect("/create?another")
    else:
        return redirect(url_for("repo.summary",
            owner=current_user.canonical_name, repo=resp["name"]))

@manage.route("/clone")
@loginrequired
def clone():
    another = request.args.get("another")
    return render_template("clone.html", another=another, visibility="UNLISTED")

@manage.route("/clone", methods=["POST"])
@loginrequired
def clone_POST():
    if not current_app.repo_api:
        abort(501)
    valid = Validation(request)
    resp = current_app.repo_api.clone_repo(valid)
    if not valid.ok:
        return render_template("clone.html", **valid.kwargs)
    return redirect(url_for("repo.summary",
        owner=current_user.canonical_name, repo=resp["name"]))

@manage.route("/<owner_name>/<repo_name>/settings/info")
@loginrequired
def settings_info(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        return redirect(url_for(".settings_info",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_info.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/info", methods=["POST"])
@loginrequired
def settings_info_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        repo = repo.new_repo

    valid = Validation(request)

    rewrite = lambda value: None if value == "" else value
    input = {
        key: rewrite(valid.source[key]) for key in [
            "description", "visibility", "HEAD",
        ] if valid.source.get(key) is not None
    }

    resp = exec_gql("git.sr.ht", """
        mutation UpdateRepository($id: Int!, $input: RepoInput!) {
            updateRepository(id: $id, input: $input) { id }
        }
    """, valid=valid, id=repo.id, input=input)
    if not valid.ok:
        return render_template("settings_info.html",
                owner=owner, repo=repo, **valid.kwargs)

    return redirect(url_for("manage.settings_info",
        owner_name=owner_name, repo_name=repo_name))

@manage.route("/<owner_name>/<repo_name>/settings/rename")
@loginrequired
def settings_rename(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        return redirect(url_for(".settings_rename",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_rename.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/rename", methods=["POST"])
@loginrequired
def settings_rename_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        repo = repo.new_repo

    valid = Validation(request)
    name = valid.require("name", friendly_name="Name")
    if not valid.ok:
        return render_template("settings_rename.html", owner=owner, repo=repo,
                **valid.kwargs)

    resp = exec_gql("git.sr.ht", """
        mutation RenameRepository($id: Int!, $name: String!) {
            updateRepository(id: $id, input: {name: $name}) {
                name
            }
        }
    """, valid=valid, id=repo.id, name=name)

    if not valid.ok:
        return render_template("settings_rename.html", owner=owner, repo=repo,
                **valid.kwargs)
    resp = resp["updateRepository"]
    return redirect(url_for("repo.summary",
        owner=owner_name, repo=resp["name"]))

@manage.route("/<owner_name>/<repo_name>/settings/access")
@loginrequired
def settings_access(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        return redirect(url_for(".settings_manage",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_access.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/access", methods=["POST"])
@loginrequired
def settings_access_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        repo = repo.new_repo
    valid = Validation(request)
    username = valid.require("user", friendly_name="User")
    mode = valid.optional("access", cls=AccessMode, default=AccessMode.ro)
    if not valid.ok:
        return render_template("settings_access.html",
                owner=owner, repo=repo, **valid.kwargs)
    # TODO: Group access
    if username[0] == "~":
        username = username[1:]
    try:
        user = current_app.oauth_service.lookup_user(username)
    except:
        user = None
    valid.expect(user, "User not found.", field="user")
    valid.expect(not user or user.id != current_user.id,
            "You can't adjust your own access controls. You always have full read/write access.",
            field="user")
    valid.expect(not user or user.user_type != UserType.unconfirmed,
            "This account has not been confirmed yet.", field="user")
    valid.expect(not user or user.user_type != UserType.suspended,
            "This account has been suspended.", field="user")
    if not valid.ok:
        return render_template("settings_access.html",
                owner=owner, repo=repo, **valid.kwargs)
    grant = (Access.query
        .filter(Access.repo_id == repo.id, Access.user_id == user.id)
    ).first()
    if not grant:
        grant = Access()
        grant.repo_id = repo.id
        grant.user_id = user.id
        db.session.add(grant)
    grant.mode = mode
    db.session.commit()
    return redirect(url_for("manage.settings_access",
        owner_name=owner.canonical_name, repo_name=repo.name))

@manage.route("/<owner_name>/<repo_name>/settings/access/revoke/<grant_id>", methods=["POST"])
@loginrequired
def settings_access_revoke_POST(owner_name, repo_name, grant_id):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        repo = repo.new_repo
    grant = (Access.query
        .filter(Access.repo_id == repo.id, Access.id == grant_id)
    ).first()
    if not grant:
        abort(404)
    db.session.delete(grant)
    db.session.commit()
    return redirect("/{}/{}/settings/access".format(
        owner.canonical_name, repo.name))

@manage.route("/<owner_name>/<repo_name>/settings/delete")
@loginrequired
def settings_delete(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        return redirect(url_for(".settings_delete",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_delete.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/delete", methods=["POST"])
@loginrequired
def settings_delete_POST(owner_name, repo_name):
    if not current_app.repo_api:
        abort(501)
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        # Normally we'd redirect but we don't want to fuck up some other repo
        abort(404)
    repo_id = repo.id
    current_app.repo_api.delete_repo(repo)
    session["notice"] = "{}/{} was deleted.".format(
        owner.canonical_name, repo.name)
    return redirect("/" + owner.canonical_name)
