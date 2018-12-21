from flask import Blueprint, request, render_template
from flask import redirect, session, url_for
from flask_login import current_user
from srht.config import cfg
from srht.database import db
from srht.flask import loginrequired
from srht.validation import Validation
from gitsrht.types import Repository, RepoVisibility, Redirect
from gitsrht.types import Access, AccessMode, User
from gitsrht.access import check_access, UserAccess
from gitsrht.repos import create_repo, rename_repo, delete_repo
import shutil

manage = Blueprint('manage', __name__)
repos_path = cfg("git.sr.ht", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

@manage.route("/create")
@loginrequired
def index():
    another = request.args.get("another")
    name = request.args.get("name")
    return render_template("create.html", another=another, repo_name=name)

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
    visibility = valid.optional("visibility",
            cls=RepoVisibility,
            default=repo.visibility)
    repo.visibility = visibility
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

@manage.route("/<owner_name>/<repo_name>/settings/access", methods=["POST"])
@loginrequired
def settings_access_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        repo = repo.new_repo
    valid = Validation(request)
    user = valid.require("user", friendly_name="User")
    mode = valid.optional("access", cls=AccessMode, default=AccessMode.ro)
    if not valid.ok:
        return render_template("settings_access.html",
                owner=owner, repo=repo, **valid.kwargs)
    # TODO: Group access
    if user[0] == "~":
        user = user[1:]
    user = User.query.filter(User.username == user).first()
    valid.expect(user,
            "I don't know this user. Have they logged into git.sr.ht before?",
            field="user")
    valid.expect(not user or user.id != current_user.id,
            "You can't adjust your own access controls. You always have full read/write access.",
            field="user")
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
    return redirect("/{}/{}/settings/access".format(
        owner.canonical_name, repo.name))

@manage.route("/<owner_name>/<repo_name>/settings/access/revoke/<grant_id>", methods=["POST"])
@loginrequired
def settings_access_revoke_POST(owner_name, repo_name, grant_id):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
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
    if isinstance(repo, Redirect):
        return redirect(url_for(".settings_delete",
            owner_name=owner_name, repo_name=repo.new_repo.name))
    return render_template("settings_delete.html", owner=owner, repo=repo)

@manage.route("/<owner_name>/<repo_name>/settings/delete", methods=["POST"])
@loginrequired
def settings_delete_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, Redirect):
        # Normally we'd redirect but we don't want to fuck up some other repo
        abort(404)
    delete_repo(repo)
    session["notice"] = "{}/{} was deleted.".format(
        owner.canonical_name, repo.name)
    return redirect("/" + owner.canonical_name)
