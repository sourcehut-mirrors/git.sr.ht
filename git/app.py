from flask import render_template, request 

import random
import sys
import os
import locale

from srht.config import cfg, cfgi
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

if not app.debug:
    @app.errorhandler(500)
    def handle_500(e):
        # shit
        try:
            db.rollback()
            db.close()
        except:
            # shit shit
            sys.exit(1)
        return render_template("internal_error.html"), 500

@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api"):
        return { "errors": [ { "reason": "404 not found" } ] }, 404
    return render_template("not_found.html"), 404
