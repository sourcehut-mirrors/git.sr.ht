import subprocess
from srht.database import db
from srht.config import cfg
from gitsrht.types import Repository, RepoVisibility
import re
import os

repos_path = cfg("cgit", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

def create_repo(valid, owner):
    repo_name = valid.require("name", friendly_name="Name")
    valid.expect(not repo_name or re.match(r'^[a-z._-][a-z0-9._-]*$', repo_name),
            "Name must match [a-z._-][a-z0-9._-]*", field="name")
    description = valid.optional("description")
    visibility = valid.optional("visibility",
            default="public",
            cls=RepoVisibility)
    repos = Repository.query.filter(Repository.owner_id == owner.id)\
            .order_by(Repository.updated.desc()).all()
    valid.expect(not repo_name or not repo_name in [r.name for r in repos],
            "This name is already in use.", field="name")

    if not valid.ok:
        return None

    repo = Repository()
    repo.name = repo_name
    repo.description = description
    repo.owner_id = owner.id
    repo.visibility = visibility
    repo.path = os.path.join(repos_path, "~" + owner.username, repo.name)
    db.session.add(repo)

    subprocess.run(["mkdir", "-p", repo.path])
    subprocess.run(["git", "init", "--bare"], cwd=repo.path)

    db.session.commit()

    subprocess.run(["git", "config", "srht.repo-id", str(repo.id)], cwd=repo.path)
    subprocess.run(["ln", "-s", post_update, os.path.join(repo.path, "hooks", "update")])
    subprocess.run(["ln", "-s", post_update, os.path.join(repo.path, "hooks", "post-update")])
    return repo
