import humanize
import os
import stat
from functools import lru_cache
from gitsrht import urls
from gitsrht.git import commit_time, trim_commit, signature_time
from gitsrht.repos import GitRepoApi
from gitsrht.service import oauth_service, webhooks_notify
from gitsrht.types import Access, Redirect, Repository, User
from scmsrht.flask import ScmSrhtFlask
from srht.config import cfg
from srht.database import DbSession
from srht.flask import session
from werkzeug.urls import url_quote

db = DbSession(cfg("git.sr.ht", "connection-string"))
db.init()

class GitApp(ScmSrhtFlask):
    def __init__(self):
        super().__init__("git.sr.ht", __name__,
                access_class=Access, redirect_class=Redirect,
                repository_class=Repository, user_class=User,
                repo_api=GitRepoApi(), oauth_service=oauth_service)

        from gitsrht.blueprints.api import plumbing, porcelain
        from gitsrht.blueprints.artifacts import artifacts
        from gitsrht.blueprints.email import mail
        from gitsrht.blueprints.manage import manage
        from gitsrht.blueprints.repo import repo
        from srht.graphql import gql_blueprint

        self.register_blueprint(plumbing)
        self.register_blueprint(porcelain)
        self.register_blueprint(mail)
        self.register_blueprint(manage)
        self.register_blueprint(repo)
        self.register_blueprint(webhooks_notify)
        self.register_blueprint(gql_blueprint)

        from gitsrht.repos import object_storage_enabled
        if object_storage_enabled:
            self.register_blueprint(artifacts)

        self.add_template_filter(urls.clone_urls)
        self.add_template_filter(urls.log_rss_url)
        self.add_template_filter(urls.refs_rss_url)
        self.add_template_filter(url_quote)

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
            }

app = GitApp()
