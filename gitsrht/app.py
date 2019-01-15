import humanize
import os
import stat
from flask import session
from functools import lru_cache
from gitsrht import urls
from gitsrht.git import commit_time, trim_commit
from gitsrht.repos import GitRepoApi
from gitsrht.types import Access, Redirect, Repository, User, OAuthToken
from scmsrht.flask import ScmSrhtFlask
from srht.config import cfg
from srht.database import DbSession
from srht.oauth import AbstractOAuthService

db = DbSession(cfg("git.sr.ht", "connection-string"))
db.init()

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

class GitApp(ScmSrhtFlask):
    def __init__(self):
        super().__init__("git.sr.ht", __name__,
                access_class=Access, redirect_class=Redirect,
                repository_class=Repository, user_class=User,
                repo_api=GitRepoApi(),
                oauth_service=GitOAuthService())

        from gitsrht.blueprints.repo import repo
        from gitsrht.blueprints.stats import stats

        self.register_blueprint(repo)
        self.register_blueprint(stats)

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
