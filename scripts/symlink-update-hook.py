#!/usr/bin/env python3
from srht.config import cfg, cfgi, load_config
load_config("git")
from srht.database import DbSession
db = DbSession(cfg("sr.ht", "connection-string"))
from gitsrht.types import Repository
db.init()
import os

post_update = cfg("git.sr.ht", "post-update-script")

for repo in Repository.query.all():
    hook = os.path.join(repo.path, "hooks", "update")
    if not os.path.islink(hook) or os.readlink(hook) != post_update:
        print("Migrating {}".format(repo.name))
        os.remove(hook)
        os.symlink(post_update, hook)
