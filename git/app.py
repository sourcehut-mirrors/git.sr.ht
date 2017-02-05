from flask import Flask, render_template, request, g, Response, redirect, url_for
from jinja2 import FileSystemLoader, ChoiceLoader

import random
import sys
import os
import locale

from git.config import cfg, cfgi
from git.db import db, init_db
from git.validation import Validation
from git.flask import MetaFlask

app = MetaFlask(__name__)
app.secret_key = cfg("server", "secret-key")
app.jinja_env.cache = None
init_db()

app.jinja_loader = ChoiceLoader([
    FileSystemLoader("overrides"),
    FileSystemLoader("templates"),
])

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

@app.context_processor
def inject():
    return {
        'root': cfg("server", "protocol") + "://" + cfg("server", "domain"),
        'domain': cfg("server", "domain"),
        'protocol': cfg("server", "protocol"),
        'len': len,
        'any': any,
        'request': request,
        'locale': locale,
        'url_for': url_for,
        'cfg': cfg,
        'cfgi': cfgi,
        'valid': Validation(request),
        'datef': lambda d: d.strftime('%Y-%m-%d %H:%M:%S UTC') if d is not None else 'Never',
    }
