from flask import session
from srht.flask import SrhtFlask
from srht.config import cfg, load_config
load_config("git")

from srht.database import DbSession
db = DbSession(cfg("sr.ht", "connection-string"))

from gitsrht.types import User
db.init()

import gitsrht.oauth
from gitsrht.blueprints.api import api
from gitsrht.blueprints.public import public
from gitsrht.blueprints.manage import manage

class GitApp(SrhtFlask):
    def __init__(self):
        super().__init__("git", __name__)

        self.register_blueprint(api)
        self.register_blueprint(public)
        self.register_blueprint(manage)

        meta_client_id = cfg("meta.sr.ht", "oauth-client-id")
        meta_client_secret = cfg("meta.sr.ht", "oauth-client-secret")
        builds_client_id = cfg("builds.sr.ht", "oauth-client-id")
        self.configure_meta_auth(meta_client_id, meta_client_secret,
                base_scopes=["profile"] + ([
                    "{}/jobs:write".format(builds_client_id)
                ] if builds_client_id else []))

        @self.context_processor
        def inject():
            notice = session.get("notice")
            if notice:
                del session["notice"]
            return {
                "notice": notice
            }

        @self.login_manager.user_loader
        def user_loader(username):
            # TODO: Switch to a session token
            return User.query.filter(User.username == username).one_or_none()

    def lookup_or_register(self, exchange, profile, scopes):
        user = User.query.filter(User.username == profile["username"]).first()
        if not user:
            user = User()
            db.session.add(user)
        user.username = profile.get("username")
        user.email = profile.get("email")
        user.paid = profile.get("paid")
        user.oauth_token = exchange["token"]
        user.oauth_token_expires = exchange["expires"]
        user.oauth_token_scopes = scopes
        db.session.commit()
        return user

app = GitApp()
