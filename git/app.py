from flask import render_template, request 

import locale

from srht.config import cfg, cfgi, load_config
load_config("git")
from srht.database import DbSession
db = DbSession(cfg("sr.ht", "connection-string"))
db.init()

from srht.flask import SrhtFlask
app = SrhtFlask("git", __name__)
app.secret_key = cfg("server", "secret-key")

try:
    locale.setlocale(locale.LC_ALL, 'en_US')
except:
    pass

from git.blueprints.cgit import cgit

app.register_blueprint(cgit)
