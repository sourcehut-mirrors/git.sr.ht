#!/usr/bin/env python3
from srht.config import cfg, cfgi, load_config
load_config("git")
from srht.database import DbSession
db = DbSession(cfg("sr.ht", "connection-string"))
from gitsrht.types import Repository
db.init()
import os

post_update = cfg("git.sr.ht", "post-update-script")

def migrate(path, link):
    if not os.path.exists(path) \
            or not os.path.islink(path) \
            or os.readlink(path) != link:
        if os.path.exists(path):
            os.remove(path)
        os.symlink(link, path)
        return True
    return False

for repo in Repository.query.all():
    if migrate(os.path.join(repo.path, "hooks", "update"), post_update) \
        or migrate(os.path.join(repo.path, "hooks", "post-update"), post_update):
        print("Migrated {}".format(repo.name))
