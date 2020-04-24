import pygit2
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from gitsrht.git import Repository as GitRepository
from gitsrht.types import User
from scmsrht.access import get_repo_or_redir
from scmsrht.stats import RepoContributions, get_contrib_chart_data

stats = Blueprint('stats', __name__)

def get_contributions(git_repo, tip, since):
    contributions = RepoContributions(User)

    since_ts = since.timestamp()
    for commit in git_repo.walk(tip.id, pygit2.GIT_SORT_TIME):
        timestamp = commit.commit_time + commit.commit_time_offset
        if timestamp < since_ts:
            break

        user = contributions.get_or_create_user(
            commit.author.email, commit.author.name)
        user.add_commit(timestamp)

    return contributions

@stats.route("/<owner>/<repo>/contributors")
def contributors(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    since = datetime.now() - timedelta(weeks=52)

    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return render_template("empty-repo.html", owner=owner, repo=repo)

        default_branch = git_repo.default_branch()
        tip = git_repo.get(default_branch.target)
        contributions = get_contributions(git_repo, tip, since)
        chart_data = get_contrib_chart_data(contributions)

    return render_template("contributors.html", view="contributors",
        owner=owner, repo=repo, chart_data=chart_data)
