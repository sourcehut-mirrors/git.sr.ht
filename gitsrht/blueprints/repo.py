import pygit2
from jinja2 import Markup
from flask import Blueprint, render_template, abort
from flask_login import current_user
from gitsrht.access import get_repo, has_access, UserAccess
from gitsrht.redis import redis
from gitsrht.git import CachedRepository, commit_time, annotate_tree
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
    key = f"git.sr.ht:git:markdown:{readme.id.hex}"
    html = redis.get(key)
    if html:
        return Markup(html.decode())
    try:
        md = repo.get(readme.id).data.decode()
    except:
        pass
    html = markdown(md, ["h1", "h2", "h3", "h4", "h5"])
    redis.setex(key, html, timedelta(days=30))
    return Markup(html)

@repo.route("/<owner>/<repo>")
def summary(owner, repo):
    owner, repo = get_repo(owner, repo)
    if not repo:
        abort(404)
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
    default_branch = git_repo.default_branch()
    tip = git_repo.get(default_branch.target)
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
    return render_template("summary.html", view="summary",
            owner=owner, repo=repo, readme=readme, commits=commits,
            clone_urls=clone_urls, latest_tag=latest_tag,
            default_branch=default_branch)

@repo.route("/<owner>/<repo>/tree", defaults={"branch": None, "path": ""})
@repo.route("/<owner>/<repo>/tree/<branch>", defaults={"path": ""})
@repo.route("/<owner>/<repo>/tree/<branch>/<path:path>")
def tree(owner, repo, branch, path):
    owner, repo = get_repo(owner, repo)
    if not repo:
        abort(404)
    if not has_access(repo, UserAccess.read):
        abort(401)
    git_repo = CachedRepository(repo.path)
    if branch is None:
        branch = git_repo.default_branch()
    else:
        branch = git_repo.branches.get(branch)
    if not branch:
        abort(404)
    commit = git_repo.get(branch.target)

    tree = commit.tree
    path = path.split("/")
    for part in path:
        if part == "":
            continue
        if part not in tree:
            abort(404)
        entry = tree[part]
        if entry.type == "blob":
            return "TODO: render blobs"
        tree = git_repo.get(entry.id)

    tree = annotate_tree(git_repo, tree, commit)
    tree = sorted(tree, key=lambda e: e.name)

    return render_template("tree.html", view="tree",
            owner=owner, repo=repo, branch=branch,
            branch_name=branch.name[len("refs/heads/"):],
            commit=commit, tree=tree, path=path)
