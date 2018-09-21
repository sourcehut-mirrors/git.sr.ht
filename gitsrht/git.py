from datetime import datetime, timedelta, timezone
from pygit2 import Repository, Tag
from functools import lru_cache

def trim_commit(msg):
    if "\n" not in msg:
        return msg
    return msg[:msg.index("\n")]

def commit_time(commit):
    author = commit.author if hasattr(commit, 'author') else commit.tagger
    # Time handling in python is so dumb
    tzinfo = timezone(timedelta(minutes=author.offset))
    tzaware = datetime.fromtimestamp(float(author.time), tzinfo)
    diff = datetime.now(timezone.utc) - tzaware
    return datetime.utcnow() - diff

@lru_cache(maxsize=256)
def CachedRepository(path):
    return _CachedRepository(path)

@lru_cache(maxsize=1024)
def _get_ref(repo, ref):
    return repo._get(ref)

class _CachedRepository(Repository):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get(self, ref):
        return _get_ref(self, ref)

    def _get(self, ref):
        return super().get(ref)

    def default_branch(self):
        branch = self.branches.get("master")
        if not branch:
            branch = list(self.branches.local)[0]
            branch = self.branches.get(branch)
        return branch
