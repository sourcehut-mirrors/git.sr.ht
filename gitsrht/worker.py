from srht.config import cfg
from srht.database import DbSession, db
if not hasattr(db, "session"):
    db = DbSession(cfg("git.sr.ht", "connection-string"))
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
import re

worker = Celery('git', broker=cfg("git.sr.ht", "redis"))
builds_sr_ht = cfg("builds.sr.ht", "origin")
builds_client_id = cfg("builds.sr.ht", "oauth-client-id")
git_sr_ht = cfg("git.sr.ht", "origin")

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
    try:
        i = text.index("\n")
    except ValueError:
        return text + "\n"
    else:
        return text[:i + 1]

def _auto_setup_sub_source(repo, m):
    sources = m.get('sources', [])
    re_repo_url = re.compile(r'^{}/(?P<usr>[^/]+)/{}/?$'.format(
        re.escape(git_sr_ht), re.escape(repo.name)))
    for i, s in enumerate(sources):
        m = re_repo_url.search(s)
        if m:
            owner = repo.owner.canonical_name
            if owner != m.group('usr'):
                new_source = '{}/{}/{}'.format(
                    git_sr_ht, repo.owner.canonical_name, repo.name)
                sources[i] = new_source
                print("auto-setup: changing source {} -> {}".format(
                    s, new_source))
                break

def _auto_setup_auto_source(repo, m):
    sources = m.setdefault('sources', [])
    this_url = '{}/{}/{}'.format(
        git_sr_ht, repo.owner.canonical_name, repo.name)
    if this_url not in sources:
        sources.append(this_url)
        print("auto-setup: adding source {}".format(this_url))

_auto_setup_funcs = {
    'sub_source': _auto_setup_sub_source,
    #'auto_source': _auto_setup_auto_source
}

def _auto_setup_manifest(repo, m):
    auto_setup = m.setdefault('autosetup', 'sub_source,auto_source')
    if not auto_setup:
        return

    if isinstance(auto_setup, str):
        auto_setup = [s.strip() for s in auto_setup.split(',')]

    for s in auto_setup:
        func = _auto_setup_funcs.get(s)
        if func:
            func(repo, m)
        else:
            print("Warning: unknown build manifest auto-setup function: {}".format(s))

def submit_builds(repo, git_repo, commit):
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
                    for blob in git_repo.get(build_dir.id)
                    if blob.type == 'blob' and (
                        blob.name.endswith('.yml')
                        or blob.name.endswith('.yaml')
                    )
                }
            )

    manifests = {}
    for name, blob in manifest_blobs.items():
        m = git_repo.get(blob.id).data.decode()
        m = yaml.safe_load(m)
        _auto_setup_manifest(repo, m)
        manifests[name] = m

    if not any(manifests):
        return

    for name, m in iter(manifests.items()):
        m = Manifest(m)
        if m.sources:
            m.sources = [source if os.path.basename(source) != repo.name
                    else source + "#" + str(commit.id) for source in m.sources]
        manifests[name] = m
    token = repo.owner.oauth_token
    scopes = repo.owner.oauth_token_scopes
    scopes = [OAuthScope(s) for s in scopes.split(",")]
    if not any(s for s in scopes
            if s.client_id == builds_client_id and s.access == 'write'):
        print("Warning: log out and back in on the website to enable builds integration")
        return
    for name, manifest in iter(manifests.items()):
        resp = do_webhook(builds_sr_ht + "/api/jobs", {
            "manifest": yaml.dump(manifest.to_dict(), default_flow_style=False),
            # TODO: orgs
            "tags": [repo.name] + [name] if name else [],
            "note": "{}\n\n[{}]({}) &mdash; [{}](mailto:{})".format(
                # TODO: cgit replacement
                html.escape(first_line(commit.message)),
                str(commit.id)[:7],
                "{}/{}/{}/commit/{}".format(
                    git_sr_ht,
                    "~" + repo.owner.username,
                    repo.name,
                    str(commit.id)),
                commit.author.name,
                commit.author.email,
            )
        }, { "Authorization": "token " + token })
        if not resp or resp.status_code != 200:
            print("Failed to submit build job" + (" " + name) if name else "")
            return
        build_id = resp.json().get("id")
        if name != ".build.yml":
            print("Build started: https://builds.sr.ht/~{}/job/{} [{}]".format(
                repo.owner.username, build_id, name))
        else:
            print("Build started: https://builds.sr.ht/~{}/job/{}".format(
                repo.owner.username, build_id))

def do_post_update(repo, git_repo, ref):
    commit = git_repo.get(ref)
    if not commit:
        return
    if isinstance(commit, Tag):
        commit = git_repo.get(commit.target)
    if not isinstance(commit, Commit):
        return
    if builds_sr_ht:
        submit_builds(repo, git_repo, commit)
