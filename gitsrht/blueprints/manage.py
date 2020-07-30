import pygit2
from flask import Blueprint, request, render_template
from flask import redirect, url_for
from gitsrht.git import Repository as GitRepository
from srht.database import db
from srht.oauth import loginrequired
from srht.validation import Validation
from scmsrht.access import check_access, UserAccess
from scmsrht.repos.redirect import BaseRedirectMixin
from scmsrht.repos.repository import RepoVisibility
from scmsrht.webhooks import UserWebhook

manage = Blueprint('manage_git', __name__)

@manage.route("/<owner_name>/<repo_name>/settings/info_git", methods=["POST"])
@loginrequired
def settings_info_git_POST(owner_name, repo_name):
    owner, repo = check_access(owner_name, repo_name, UserAccess.manage)
    if isinstance(repo, BaseRedirectMixin):
        repo = repo.new_repo
    valid = Validation(request)
    desc = valid.optional("description", default=repo.description)
    visibility = valid.optional("visibility",
            cls=RepoVisibility,
            default=repo.visibility)
    branch = valid.optional("default_branch_name")
    with GitRepository(repo.path) as git_repo:
        new_default_branch = None
        if branch:
            try:
                new_default_branch = git_repo.branches.get(branch)
            except pygit2.InvalidSpecError:
                valid.error(f"Branch {branch} not found", field="default_branch_name")
        if not valid.ok:
            return render_template("settings_info.html",
                    owner=owner, repo=repo, **valid.kwargs)
        if new_default_branch:
            head_ref = git_repo.lookup_reference("HEAD")
            head_ref.set_target(new_default_branch.name)

        repo.visibility = visibility
        repo.description = desc
        UserWebhook.deliver(UserWebhook.Events.repo_update,
                repo.to_dict(), UserWebhook.Subscription.user_id == repo.owner_id)
        db.session.commit()
        return redirect(url_for("manage.settings_info",
            owner_name=owner_name, repo_name=repo_name))
