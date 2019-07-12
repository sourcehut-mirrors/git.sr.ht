import humanize
import os
import stat
from functools import lru_cache
from gitsrht import urls
from gitsrht.git import commit_time, trim_commit
from gitsrht.repos import GitRepoApi
from gitsrht.service import oauth_service, webhooks_notify
from gitsrht.types import Access, Redirect, Repository, User
from scmsrht.flask import ScmSrhtFlask
from srht.config import cfg
from srht.database import DbSession
from srht.flask import session

db = DbSession(cfg("git.sr.ht", "connection-string"))
db.init()

class GitApp(ScmSrhtFlask):
    def __init__(self):
        super().__init__("git.sr.ht", __name__,
                access_class=Access, redirect_class=Redirect,
                repository_class=Repository, user_class=User,
                repo_api=GitRepoApi(), oauth_service=oauth_service)

        from gitsrht.blueprints.api import data
        from gitsrht.blueprints.repo import repo
        from gitsrht.blueprints.stats import stats

        self.register_blueprint(data)
        self.register_blueprint(repo)
        self.register_blueprint(stats)
        self.register_blueprint(webhooks_notify)

        self.add_template_filter(urls.clone_urls)
        self.add_template_filter(urls.log_rss_url)
        self.add_template_filter(urls.refs_rss_url)

        @self.context_processor
        def inject():
            notice = session.get("notice")
            if notice:
                del session["notice"]
            return {
                "commit_time": commit_time,
                "trim_commit": trim_commit,
                "humanize": humanize,
                "stat": stat,
                "notice": notice,
                "path_join": os.path.join
            }

app = GitApp()
