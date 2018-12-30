import humanize
import stat
import os
from flask import session
from functools import lru_cache
from srht.flask import SrhtFlask
from srht.config import cfg
from srht.database import DbSession

db = DbSession(cfg("git.sr.ht", "connection-string"))

from gitsrht.types import User

db.init()

from gitsrht import urls
from gitsrht.oauth import GitOAuthService
from gitsrht.git import commit_time, trim_commit

def lookup_user(email):
    return User.query.filter(User.email == email).one_or_none()

class GitApp(SrhtFlask):
    def __init__(self):
        super().__init__("git.sr.ht", __name__,
                oauth_service=GitOAuthService())

        self.url_map.strict_slashes = False

        from gitsrht.blueprints.api import api
        from gitsrht.blueprints.public import public
        from gitsrht.blueprints.repo import repo
        from gitsrht.blueprints.stats import stats
        from gitsrht.blueprints.manage import manage

        self.register_blueprint(api)
        self.register_blueprint(public)
        self.register_blueprint(repo)
        self.register_blueprint(stats)
        self.register_blueprint(manage)

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
                "lookup_user": lookup_user,
                "stat": stat,
                "notice": notice,
                "path_join": os.path.join
            }

        @self.login_manager.user_loader
        def user_loader(username):
            # TODO: Switch to a session token
            return User.query.filter(User.username == username).one_or_none()

app = GitApp()
