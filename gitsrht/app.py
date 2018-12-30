import humanize
import stat
import os
from flask import session
from functools import lru_cache
from srht.flask import SrhtFlask
from srht.config import cfg
from srht.database import DbSession
from srht.oauth import AbstractOAuthService

db = DbSession(cfg("git.sr.ht", "connection-string"))

from gitsrht.types import User, OAuthToken

db.init()

from gitsrht import urls
from gitsrht.git import commit_time, trim_commit

def lookup_user(email):
    return User.query.filter(User.email == email).one_or_none()

client_id = cfg("git.sr.ht", "oauth-client-id")
client_secret = cfg("git.sr.ht", "oauth-client-secret")
builds_client_id = cfg("builds.sr.ht", "oauth-client-id", default=None)

class GitOAuthService(AbstractOAuthService):
    def __init__(self):
        super().__init__(client_id, client_secret,
                required_scopes=["profile"] + ([
                    "{}/jobs:write".format(builds_client_id)
                ] if builds_client_id else []),
                token_class=OAuthToken, user_class=User)

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

app = GitApp()
