import pygit2
from collections import defaultdict
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template
from functools import lru_cache
from gitsrht.git import Repository as GitRepository
from gitsrht.types import User
from scmsrht.access import get_repo_or_redir

stats = Blueprint('stats', __name__)

def _week(time):
    """Used to group contributions by week"""
    return time.strftime('%Y/%W')

@lru_cache(maxsize=256)
def _user(email, name):
    """Used to grouped contributions by either username or email."""
    email = email.lower()
    user = User.query.filter_by(email=email).one_or_none()
    return (None, name, user.username) if user else (email, name, None)

def get_contributions(git_repo, tip, since):
    contributions = defaultdict(lambda: {
        "commits": 0,
        "weekly": defaultdict(lambda: 0)
    })

    since_ts = since.timestamp()
    for commit in git_repo.walk(tip.id, pygit2.GIT_SORT_TIME):
        timestamp = commit.commit_time + commit.commit_time_offset
        if timestamp < since_ts:
            break

        week = _week(datetime.fromtimestamp(timestamp))
        user = _user(commit.author.email, commit.author.name)
        contributions[user]['commits'] += 1
        contributions[user]['weekly'][week] += 1

    return contributions

def get_contrib_chart_data(contributions):
    # Max number of commits by a contributor in a single week
    try:
        max_commits = max(
            max(commits for _, commits in data['weekly'].items())
            for _, data in contributions.items())
    except:
        max_commits = 0

    all_weeks = [_week(date.today() - timedelta(weeks=51 - n))
        for n in range(52)]

    def bars(contributions):
        bars = list()
        for ordinal, week in enumerate(all_weeks):
            if week in contributions:
                week_commits = contributions[week]
                bars.append({
                    "ordinal": ordinal,
                    "week": week,
                    "commits": week_commits,
                    "height": 100 * week_commits // max_commits
                })
        return bars

    chart_data = [
        (email, full_name, username, data['commits'], bars(data['weekly']))
        for (email, full_name, username), data in contributions.items()]
    return sorted(chart_data, key=lambda x: x[3], reverse=True)

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
