import humanize
import os
import stat
from functools import lru_cache
from gitsrht import urls
from gitsrht.git import commit_time, commit_links, trim_commit, signature_time
from gitsrht.service import oauth_service
from gitsrht.types import User
from srht.config import cfg
from srht.database import db, DbSession
from srht.flask import SrhtFlask, session
from jinja2 import FileSystemLoader, ChoiceLoader
from urllib.parse import quote as url_quote

db = DbSession(cfg("git.sr.ht", "connection-string"))
db.init()

class GitApp(SrhtFlask):
    def __init__(self):
        super().__init__("git.sr.ht", __name__,
                oauth_service=oauth_service)

        self.url_map.strict_slashes = False

        from gitsrht.blueprints.public import public
        from gitsrht.blueprints.api import register_api
        from gitsrht.blueprints.api.plumbing import plumbing
        from gitsrht.blueprints.api.porcelain import porcelain
        from gitsrht.blueprints.artifacts import artifacts
        from gitsrht.blueprints.email import mail
        from gitsrht.blueprints.manage import manage
        from gitsrht.blueprints.repo import repo
        from srht.graphql import gql_blueprint

        self.register_blueprint(public)

        register_api(self)
        self.register_blueprint(plumbing)
        self.register_blueprint(porcelain)
        self.register_blueprint(mail)
        self.register_blueprint(manage)
        self.register_blueprint(repo)
        self.register_blueprint(gql_blueprint)

        from gitsrht.repos import object_storage_enabled
        if object_storage_enabled:
            self.register_blueprint(artifacts)

        self.add_template_filter(urls.clone_urls)
        self.add_template_filter(urls.log_rss_url)
        self.add_template_filter(urls.refs_rss_url)
        self.add_template_filter(url_quote, name="url_quote")
        self.add_template_filter(commit_links)

        from gitsrht.webhooks import webhook_metrics_collector
        self.metrics_registry.register(webhook_metrics_collector)

        @self.context_processor
        def inject():
            notice = session.get("notice")
            if notice:
                del session["notice"]
            return {
                "commit_time": commit_time,
                "signature_time": signature_time,
                "humanize": humanize,
                "notice": notice,
                "object_storage_enabled": object_storage_enabled,
                "path_join": os.path.join,
                "stat": stat,
                "trim_commit": trim_commit,
                "lookup_user": self.lookup_user
            }

        choices = [self.jinja_loader, FileSystemLoader(os.path.join(
            os.path.dirname(__file__), "templates"))]
        self.jinja_loader = ChoiceLoader(choices)

    def lookup_user(self, email):
        return User.query.filter(User.email == email).one_or_none()

app = GitApp()
