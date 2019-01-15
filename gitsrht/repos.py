import subprocess
from gitsrht.types import Repository, Redirect
from scmsrht.repos import SimpleRepoApi
from srht.config import cfg
import os.path

repos_path = cfg("git.sr.ht", "repos")
post_update = cfg("git.sr.ht", "post-update-script")

class GitRepoApi(SimpleRepoApi):
    def __init__(self):
        super().__init__(repos_path,
                redirect_class=Redirect,
                repository_class=Repository)

    def do_init_repo(self, owner, repo):
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
