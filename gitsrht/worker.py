from srht.config import cfg, load_config, loaded
if not loaded():
    load_config("git")
from srht.database import DbSession, db
if not hasattr(db, "session"):
    db = DbSession(cfg("sr.ht", "connection-string"))
    import gitsrht.types
    db.init()

from celery import Celery
from pygit2 import Commit, Tag
from srht.oauth import OAuthScope
from buildsrht.manifest import Manifest
import requests
import html
import yaml
import os

worker = Celery('git', broker=cfg("git.sr.ht", "redis"))
builds_sr_ht = cfg("network", "builds")
builds_client_id = cfg("builds.sr.ht", "oauth-client-id")
git_sr_ht = cfg("server", "protocol") + "://" + cfg("server", "domain")

@worker.task
def _do_webhook(url, payload, headers=None, **kwargs):
    if "timeout" not in kwargs:
        kwargs["timeout"] = 15
    return requests.post(url, json=payload, headers=headers, **kwargs)
    # TODO: Store the response somewhere I guess

def do_webhook(url, payload, headers=None):
    try:
        return _do_webhook(url, payload, headers, timeout=3)
    except requests.exceptions.Timeout:
        _do_webhook.delay(url, payload, headers)
        return None

def first_line(text):
    return text[:text.index("\n") + 1]

def do_post_update(repo, git_repo, ref):
    commit = git_repo.get(ref)
    if not commit:
        return
    if isinstance(commit, Tag):
        commit = git_repo.get(commit.target)
    if not isinstance(commit, Commit):
        return

    # builds.sr.ht
    if builds_sr_ht:
        manifest = None
        if ".build.yml" in commit.tree:
            manifest = commit.tree[".build.yml"]
        if ".build.yaml" in commit.tree:
            manifest = commit.tree[".build.yaml"]
        # TODO: More complex build manifests
        if manifest:
            manifest = git_repo.get(manifest.id)
            manifest = manifest.data.decode()
            manifest = Manifest(yaml.safe_load(manifest))
            manifest.sources = [
                source if os.path.basename(source) != repo.name else source + "#" + str(ref)
                for source in manifest.sources
            ]
            token = repo.owner.oauth_token
            scopes = repo.owner.oauth_token_scopes
            scopes = [OAuthScope(s) for s in scopes.split(",")]
            if not any(s for s in scopes
                    if s.client_id == builds_client_id and s.access == 'write'):
                print("Warning: log out and back in on the website to enable builds integration")
            else:
                resp = do_webhook(builds_sr_ht + "/api/jobs", {
                    "manifest": yaml.dump(manifest.to_dict(), default_flow_style=False),
                    # TODO: orgs
                    "tags": [repo.name],
                    "note": "{}\n\n[{}]({}) &mdash; [{}](mailto:{})".format(
                        # TODO: cgit replacement
                        html.escape(first_line(commit.message)),
                        str(commit.id)[:7],
                        "{}/{}/{}/commit?id={}".format(
                            git_sr_ht,
                            "~" + repo.owner.username,
                            repo.name,
                            str(commit.id)),
                        commit.author.name,
                        commit.author.email,
                    )
                }, { "Authorization": "token " + token })
                if resp:
                    build_id = resp.json().get("id")
                    print("Build started: https://builds.sr.ht/job/{}".format(build_id))
