import html
import os
import re
from pygit2 import Repository as GitRepository, Commit, Tag
from gitsrht.blueprints.api import commit_to_dict
from gitsrht.types import User, Repository
from scmsrht.redis import redis
from scmsrht.repos import RepoVisibility
from scmsrht.submit import BuildSubmitterBase
from gitsrht.webhooks import RepoWebhook
from srht.config import cfg, get_origin
from srht.database import db
from urllib.parse import urlparse

builds_sr_ht = cfg("builds.sr.ht", "origin", None)
git_sr_ht = get_origin("git.sr.ht", external=True)

def first_line(text):
    try:
        i = text.index("\n")
    except ValueError:
        return text + "\n"
    else:
        return text[:i + 1]

class GitBuildSubmitter(BuildSubmitterBase):
    def __init__(self, repo, git_repo):
        super().__init__(git_sr_ht, 'git', repo)
        self.git_repo = git_repo

    def find_manifests(self, commit):
        manifest_blobs = dict()
        if ".build.yml" in commit.tree:
            build_yml = commit.tree[".build.yml"]
            if build_yml.type == 'blob':
                manifest_blobs[".build.yml"] = build_yml
        elif ".builds"  in commit.tree:
            build_dir = commit.tree[".builds"]
            if build_dir.type == 'tree':
                manifest_blobs.update(
                    {
                        blob.name: blob
                        for blob in self.git_repo.get(build_dir.id)
                        if blob.type == 'blob' and (
                            blob.name.endswith('.yml')
                            or blob.name.endswith('.yaml')
                        )
                    }
                )

        manifests = {}
        for name, blob in manifest_blobs.items():
            m = self.git_repo.get(blob.id).data.decode()
            manifests[name] = m
        return manifests

    def get_commit_id(self, commit):
        return str(commit.id)

    def get_commit_note(self, commit):
        return "[{}]({}) &mdash; [{}](mailto:{})\n\n{}".format(
            str(commit.id)[:7],
            "{}/{}/{}/commit/{}".format(
                git_sr_ht,
                "~" + self.repo.owner.username,
                self.repo.name,
                str(commit.id)),
            commit.author.name,
            commit.author.email,
            "<pre>" + html.escape(first_line(commit.message)) + "</pre>",
        )

    def get_clone_url(self):
        origin = get_origin("git.sr.ht", external=True)
        owner_name = self.repo.owner.canonical_name
        repo_name = self.repo.name
        if self.repo.visibility == RepoVisibility.private:
            # Use SSH URL
            origin = origin.replace("http://", "").replace("https://", "")
            return f"git+ssh://git@{origin}/{owner_name}/{repo_name}"
        else:
            # Use http(s) URL
            return f"{origin}/{owner_name}/{repo_name}"

# https://stackoverflow.com/a/14693789
ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def do_post_update(context, refs):
    global db
    # TODO: we shouldn't need this once we move most of this shit to the
    # internal API
    if not hasattr(db, "session"):
        import gitsrht.types
        from srht.database import DbSession
        db = DbSession(cfg("git.sr.ht", "connection-string"))
        db.init()

    uid = os.environ.get("SRHT_UID")
    push = os.environ.get("SRHT_PUSH")
    user = context["user"]
    repo = context["repo"]

    payload = {
        "push": push,
        "pusher": user,
        "refs": list(),
    }

    git_repo = GitRepository(repo["path"])
    oids = set()
    for ref in refs:
        update = redis.get(f"update.{push}.{ref}")
        if update:
            old, new = update.decode().split(":")
            old = git_repo.get(old)
            new = git_repo.get(new)
            update = dict()
            if isinstance(new, Tag):
                update.update({
                    "annotated_tag": {
                        "name": new.name,
                        "message": new.message,
                    },
                })
                new = git_repo.get(new.target)
            update.update({
                "name": ref,
                "old": commit_to_dict(old) if old else None,
                "new": commit_to_dict(new) if new else None,
            })
            payload["refs"].append(update)

        try:
            if re.match(r"^[0-9a-z]{40}$", ref): # commit
                commit = git_repo.get(ref)
            elif ref.startswith("refs/"): # ref
                target_id = git_repo.lookup_reference(ref).target
                commit = git_repo.get(target_id)
                if isinstance(commit, Tag):
                    commit = git_repo.get(commit.target)
            else:
                continue
            if not isinstance(commit, Commit):
                continue
            if commit.id in oids:
                continue
            oids.add(commit.id)
        except:
            continue

        if builds_sr_ht:
            # TODO: move this to internal API
            r = Repository.query.get(repo["id"])
            s = GitBuildSubmitter(r, git_repo)
            res = s.submit(commit)
            if res.status != 'skipped':
                res.printmsgs()

    # TODO: get these from internal API
    # sync webhooks
    for resp in RepoWebhook.deliver(RepoWebhook.Events.repo_post_update, payload,
            RepoWebhook.Subscription.repo_id == repo["id"],
            RepoWebhook.Subscription.sync,
            delay=False):
        if resp == None:
            # TODO: Add details?
            print("Error submitting webhook")
            continue
        if resp.status_code != 200:
            print(f"Webhook returned status {resp.status_code}")
        try:
            print(ansi_escape.sub('', resp.text))
        except:
            print("Unable to decode webhook response")
    # async webhooks
    RepoWebhook.deliver(RepoWebhook.Events.repo_post_update, payload,
            RepoWebhook.Subscription.repo_id == repo["id"],
            RepoWebhook.Subscription.sync == False)
