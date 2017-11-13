import subprocess
from srht.database import db
from srht.config import cfg
from gitsrht.types import Repository, RepoVisibility, Redirect
import shutil
import re
import os

repos_path = cfg("cgit", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

def validate_name(valid, owner, repo_name):
    if not valid.ok:
        return None
    valid.expect(re.match(r'^[a-z._-][a-z0-9._-]*$', repo_name),
            "Name must match [a-z._-][a-z0-9._-]*", field="name")
    existing = (Repository.query
            .filter(Repository.owner_id == owner.id)
            .filter(Repository.name.ilike("%" + repo_name + "%"))
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
        repo.description = description
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
    shutil.rmtree(repo.path)
    db.session.delete(repo)
    db.session.commit()
