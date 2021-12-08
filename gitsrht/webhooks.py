from srht.config import cfg
from srht.database import DbSession, db
if not hasattr(db, "session"):
    # Initialize the database if not already configured (for running daemon)
    db = DbSession(cfg("git.sr.ht", "connection-string"))
    import gitsrht.types
    db.init()
from srht.webhook import Event
from srht.webhook.celery import CeleryWebhook, make_worker
from srht.metrics import RedisQueueCollector
from scmsrht.webhooks import UserWebhook
import sqlalchemy as sa

webhook_broker = cfg("git.sr.ht", "webhooks")
worker = make_worker(broker=webhook_broker)
webhook_metrics_collector = RedisQueueCollector(webhook_broker, "srht_webhooks", "Webhook queue length")

class RepoWebhook(CeleryWebhook):
    events = [
        Event("repo:post-update", "data:read"),
    ]

    sync = sa.Column(sa.Boolean, nullable=False, server_default="f")
    """
    If true, this webhook will be run syncronously during a git push, and
    the response text printed to the console of the pushing user.
    """

    repo_id = sa.Column(sa.Integer,
            sa.ForeignKey('repository.id', ondelete="CASCADE"), nullable=False)
    repo = sa.orm.relationship('Repository')
