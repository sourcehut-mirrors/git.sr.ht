import html
import os
import os.path
import re
import requests
import yaml
from buildsrht.manifest import Manifest
from pygit2 import Repository as GitRepository, Commit, Tag
from scmsrht.worker import BuildSubmitterBase
from srht.config import cfg
from srht.database import db
from srht.oauth import OAuthScope
from urllib.parse import urlparse

if not hasattr(db, "session"):
    import gitsrht.types
    from srht.database import DbSession
    db = DbSession(cfg("git.sr.ht", "connection-string"))
    db.init()

builds_sr_ht = cfg("builds.sr.ht", "origin")
builds_client_id = cfg("builds.sr.ht", "oauth-client-id")
git_sr_ht = cfg("git.sr.ht", "origin")

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
        return "{}\n\n[{}]({}) &mdash; [{}](mailto:{})".format(
            # TODO: cgit replacement
            html.escape(first_line(commit.message)),
            str(commit.id)[:7],
            "{}/{}/{}/commit/{}".format(
                git_sr_ht,
                "~" + self.repo.owner.username,
                self.repo.name,
                str(commit.id)),
            commit.author.name,
            commit.author.email,
        )

def do_post_update(repo, refs):
    if not builds_sr_ht:
        return False

    git_repo = GitRepository(repo.path)
    oids = set()
    for ref in refs:
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
            s = GitBuildSubmitter(repo, git_repo)
            s.submit(commit)
