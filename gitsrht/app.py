from flask import render_template, request, session
from flask_login import LoginManager, current_user
import urllib.parse
import locale

from srht.config import cfg, cfgi, load_config
load_config("git")
from srht.database import DbSession
db = DbSession(cfg("sr.ht", "connection-string"))
from gitsrht.types import User
db.init()

from srht.flask import SrhtFlask
app = SrhtFlask("git", __name__)
app.secret_key = cfg("server", "secret-key")
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(username):
    return User.query.filter(User.username == username).first()

login_manager.anonymous_user = lambda: None

try:
    locale.setlocale(locale.LC_ALL, 'en_US')
except:
    pass

meta_sr_ht = cfg("network", "meta")
meta_client_id = cfg("meta.sr.ht", "oauth-client-id")
builds_sr_ht = cfg("builds.sr.ht", "oauth-client-id")

def oauth_url(return_to):
    return "{}/oauth/authorize?client_id={}&scopes=profile,keys{}&state={}".format(
        meta_sr_ht, meta_client_id,
        "," + builds_sr_ht + "/jobs:write" if builds_sr_ht else "",
        urllib.parse.quote_plus(return_to))

from gitsrht.blueprints.auth import auth
from gitsrht.blueprints.public import public
from gitsrht.blueprints.manage import manage

app.register_blueprint(auth)
app.register_blueprint(public)
app.register_blueprint(manage)

@app.context_processor
def inject():
    notice = session.get("notice")
    if notice:
        del session["notice"]
    return {
        "oauth_url": oauth_url(request.full_path),
        "current_user": User.query.filter(User.id == current_user.id).first() \
                if current_user else None,
        "notice": notice
    }
