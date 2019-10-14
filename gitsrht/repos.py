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
        subprocess.run(["mkdir", "-p", repo.path], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "init", "--bare"], cwd=repo.path, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "srht.repo-id", str(repo.id)], check=True,
            cwd=repo.path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "update")
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "post-update")
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def do_delete_repo(self, repo):
        from gitsrht.webhooks import RepoWebhook
        RepoWebhook.Subscription.query.filter(
                RepoWebhook.Subscription.repo_id == repo.id).delete()
        super().do_delete_repo(repo)

    def do_clone_repo(self, source, repo):
        subprocess.run(["mkdir", "-p", repo.path], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "clone", "--bare", source, repo.path])
        subprocess.run(["git", "config", "srht.repo-id", str(repo.id)], check=True,
            cwd=repo.path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "update")
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ln", "-s",
                post_update,
                os.path.join(repo.path, "hooks", "post-update")
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
