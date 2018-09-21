from collections import deque
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from gitsrht.redis import redis
from pygit2 import Repository, Tag
import json

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

class AnnotatedTreeEntry:
    def __init__(self, repo, entry):
        self._entry = entry
        self._repo = repo
        if entry:
            self.id = entry.id.hex
            self.name = entry.name
            self.type = entry.type
            self.filemode = entry.filemode

    def fetch_blob(self):
        if self.type == "tree":
            self.tree = self._repo.get(self.id)
        else:
            self.blob = self._repo.get(self.id)
        return self

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "filemode": self.filemode,
            "commit": (self.commit.id.hex
                if hasattr(self, "commit") and self.commit else None),
        }

    @staticmethod
    def deserialize(res, repo):
        _id = res["id"]
        self = AnnotatedTreeEntry(repo, None)
        self.id = res["id"]
        self.name = res["name"]
        self.type = res["type"]
        self.filemode = res["filemode"]
        self.commit = repo.get(res["commit"]) if "commit" in res else None
        return self

    def __hash__(self):
        return hash(f"{self.id}:{self.name}")

    def __eq__(self, other):
        return self.id == other.id and self.name == other.name

    def __repr__(self):
        return f"<AnnotatedTreeEntry {self.name} {self.id}>"

def annotate_tree(repo, commit):
    key = f"git.sr.ht:git:tree:{commit.tree.id.hex}"
    cache = redis.get(key)
    if cache:
        cache = json.loads(cache.decode())
        return [AnnotatedTreeEntry.deserialize(
            e, repo).fetch_blob() for e in cache.values()]

    tree = { entry.id.hex: AnnotatedTreeEntry(
        repo, entry) for entry in commit.tree }

    parents = deque(commit.parents)
    left_tree = set(v for v in tree.values())
    unfinished = set(left_tree)
    if not any(commit.parents):
        return [entry.fetch_blob() for entry in tree.values()]
    parent = commit.parents[0]

    while any(unfinished):
        right_tree = { entry.id.hex: AnnotatedTreeEntry(repo, entry)
                for entry in parent.tree }
        right_tree = set(v for v in right_tree.values())
        diff = left_tree - right_tree
        for entry in diff:
            if entry.id in tree:
                tree[entry.id].commit = commit
        unfinished = unfinished - diff
        left_tree = right_tree
        commit = parent
        if not any(commit.parents):
            break
        parent = commit.parents[0]

    cache = {entry.name: entry.serialize() for entry in tree.values()}
    cache = json.dumps(cache)
    redis.setex(key, cache, timedelta(days=30))

    return [entry.fetch_blob() for entry in tree.values()]
