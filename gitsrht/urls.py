from flask import url_for
from srht.config import cfg

def clone_urls(repo):
    """Returns the readonly and read/write URL for a given repo."""
    base = (cfg("git.sr.ht", "origin")
        .replace("http://", "")
        .replace("https://", ""))

    return [
        url.format(base, repo.owner.canonical_name, repo.name)
        for url in ["https://{}/{}/{}", "git@{}:{}/{}"]
    ]

def log_rss_url(repo, ref=None):
    ref = ref if ref != "master" else None
    return url_for("repo.log_rss",
        owner=repo.owner.canonical_name,
        repo=repo.name,
        ref=ref)

def refs_rss_url(repo):
    return url_for("repo.refs_rss",
        owner=repo.owner.canonical_name,
        repo=repo.name)
