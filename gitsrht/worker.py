from srht.config import cfg, load_config, loaded
if not loaded():
    load_config("git")
from srht.database import DbSession, db
if not hasattr(db, "session"):
    db = DbSession(cfg("sr.ht", "connection-string"))
    import gitsrht.types
    db.init()

import requests
from celery import Celery
from pygit2 import Commit
from srht.oauth import OAuthScope
#from buildsrht.manifest import Manifest

worker = Celery('git', broker=cfg("git.sr.ht", "redis"))
builds_sr_ht = cfg("network", "builds")
builds_client_id = cfg("builds.sr.ht", "oauth-client-id")
git_sr_ht = cfg("server", "protocol") + "://" + cfg("server", "domain")

@worker.task
def do_webhook(url, payload, headers=None):
    r = requests.post(url, json=payload, headers=headers)
    # TODO: Store the response somewhere I guess
    print(r.status_code)
    try:
        print(r.json())
    except:
        pass

def first_line(text):
    return text[:text.index("\n") + 1]

def do_post_update(repo, git_repo, ref):
    commit = git_repo.get(ref)
    if not commit or not isinstance(commit, Commit):
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
            # TODO: parse manifest and print errors here, and update the repo URL to match the ref
            #manifest = Manifest(manifest)
            token = repo.owner.oauth_token
            scopes = repo.owner.oauth_token_scopes
            scopes = [OAuthScope(s) for s in scopes.split(",")]
            if not any(s for s in scopes
                    if s.client_id == builds_client_id and s.access == 'write'):
                print("Warning: log out and back in on the website to enable builds integration")
            else:
                do_webhook.delay(builds_sr_ht + "/api/jobs", {
                    "manifest": manifest,
                    # TODO: orgs
                    "tags": [repo.name],
                    "note": "[{}]({}) &mdash; {} &mdash; {} <{}>".format(
                        # TODO: cgit replacement
                        str(commit.id)[:7],
                        "{}/{}/{}/commit?id={}".format(
                            git_sr_ht,
                            "~" + repo.owner.username,
                            repo.name,
                            str(commit.id)),
                        first_line(commit.message),
                        commit.author.name,
                        commit.author.email,
                    )
                }, { "Authorization": "token " + token })
