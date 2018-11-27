import subprocess
from flask import redirect, abort, url_for, request
from gitsrht.access import get_repo, has_access, UserAccess
from gitsrht.types import User, Repository, RepoVisibility, Redirect
from srht.database import db
from srht.config import cfg
import shutil
import re
import os

repos_path = cfg("git.sr.ht", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

def validate_name(valid, owner, repo_name):
    if not valid.ok:
        return None
    valid.expect(re.match(r'^[a-z._-][a-z0-9._-]*$', repo_name),
            "Name must match [a-z._-][a-z0-9._-]*", field="name")
    existing = (Repository.query
            .filter(Repository.owner_id == owner.id)
            .filter(Repository.name.ilike(repo_name))
            .first())
    if existing and existing.visibility == RepoVisibility.autocreated:
        return existing
    valid.expect(not existing, "This name is already in use.", field="name")
    return None

def create_repo(valid, owner):
    repo_name = valid.require("name", friendly_name="Name")
    description = valid.optional("description")
    visibility = valid.optional("visibility",
            default="public",
            cls=RepoVisibility)
    repo = validate_name(valid, owner, repo_name)
    if not valid.ok:
        return None

    if not repo:
        repo = Repository()
        repo.name = repo_name
        repo.owner_id = owner.id
        repo.path = os.path.join(repos_path, "~" + owner.username, repo.name)
        db.session.add(repo)
        db.session.flush()

        subprocess.run(["mkdir", "-p", repo.path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "init", "--bare"], cwd=repo.path,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "srht.repo-id", str(repo.id)],
            cwd=repo.path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "update")
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "post-update")
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    repo.description = description
    repo.visibility = visibility
    db.session.commit()
    return repo

def rename_repo(owner, repo, valid):
    repo_name = valid.require("name")
    valid.expect(repo.name != repo_name,
            "This is the same name as before.", field="name")
    if not valid.ok:
        return None
    validate_name(valid, owner, repo_name)
    if not valid.ok:
        return None

    _redirect = Redirect()
    _redirect.name = repo.name
    _redirect.path = repo.path
    _redirect.owner_id = repo.owner_id
    _redirect.new_repo_id = repo.id
    db.session.add(_redirect)

    new_path = os.path.join(repos_path, "~" + owner.username, repo_name)

    subprocess.run(["mv", repo.path, new_path])

    repo.path = new_path
    repo.name = repo_name
    db.session.commit()
    return repo

def delete_repo(repo):
    try:
        shutil.rmtree(repo.path)
    except FileNotFoundError:
        pass
    db.session.delete(repo)
    db.session.commit()

def get_repo_or_redir(owner, repo):
    owner, repo = get_repo(owner, repo)
    if not repo:
        abort(404)
    if not has_access(repo, UserAccess.read):
        abort(401)
    if isinstance(repo, Redirect):
        view_args = request.view_args
        if not "repo" in view_args or not "owner" in view_args:
            return redirect(url_for(".summary",
                owner=repo.new_repo.owner.canonical_name,
                repo=repo.new_repo.name))
        view_args["owner"] = repo.new_repo.owner.canonical_name
        view_args["repo"] = repo.new_repo.name
        abort(redirect(url_for(request.endpoint, **view_args)))
    return owner, repo
