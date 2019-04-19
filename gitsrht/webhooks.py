from srht.config import cfg
from srht.database import DbSession, db
if not hasattr(db, "session"):
    # Initialize the database if not already configured (for running daemon)
    db = DbSession(cfg("git.sr.ht", "connection-string"))
    import gitsrht.types
    db.init()
from srht.webhook.celery import make_worker
from scmsrht.webhooks import RepoWebhook

worker = make_worker(broker=cfg("git.sr.ht", "webhooks"))
