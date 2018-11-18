from flask import url_for

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
