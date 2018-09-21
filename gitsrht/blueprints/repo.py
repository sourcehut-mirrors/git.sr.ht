import pygit2
from jinja2 import Markup
from flask import Blueprint, render_template, abort
from flask_login import current_user
from gitsrht.access import get_repo, has_access, UserAccess
from gitsrht.redis import redis
from gitsrht.git import CachedRepository, commit_time
from gitsrht.types import User, Repository
from srht.config import cfg
from srht.markdown import markdown
from datetime import datetime, timedelta

repo = Blueprint('repo', __name__)

def get_readme(repo, tip):
    if not tip or not "README.md" in tip.tree:
        return None
    readme = tip.tree["README.md"]
    if readme.type != "blob":
        return None
    html = redis.get(readme.id.hex)
    if html:
        return Markup(html.decode())
    try:
        md = repo.get(readme.id).data.decode()
    except:
        pass
    html = markdown(md, ["h1", "h2", "h3", "h4", "h5"])
    redis.setex(readme.id.hex, html, timedelta(days=30))
    return Markup(html)

@repo.route("/<owner>/<repo>")
def summary(owner, repo):
    owner, repo = get_repo(owner, repo)
    if not has_access(repo, UserAccess.read):
        abort(401)
    git_repo = CachedRepository(repo.path)
    base = (cfg("git.sr.ht", "origin")
        .replace("http://", "")
        .replace("https://", ""))
    clone_urls = [
        url.format(base, owner.canonical_name, repo.name)
        for url in ["https://{}/{}/{}", "git@{}:{}/{}"]
    ]
    if git_repo.is_empty:
        return render_template("empty-repo.html", owner=owner, repo=repo,
                clone_urls=clone_urls)
    master = git_repo.branches.get("master")
    if not master:
        master = list(git_repo.branches.local)[0]
        master = git_repo.branches.get(master)
    tip = git_repo.get(master.target)
    commits = list()
    for commit in git_repo.walk(tip.id, pygit2.GIT_SORT_TIME):
        commits.append(commit)
        if len(commits) >= 3:
            break
    readme = get_readme(git_repo, tip)
    tags = [(ref, git_repo.get(git_repo.references[ref].target))
        for ref in git_repo.listall_references()
        if ref.startswith("refs/tags/")]
    tags = sorted(tags, key=lambda c: commit_time(c[1]), reverse=True)
    latest_tag = tags[0] if len(tags) else None
    default_branch = master
    return render_template("summary.html", owner=owner, repo=repo,
            readme=readme, commits=commits, clone_urls=clone_urls,
            latest_tag=latest_tag, default_branch=master)
