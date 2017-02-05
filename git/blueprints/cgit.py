from flask import Blueprint, request, render_template
import requests
from git.config import cfg

cgit = Blueprint('cgit', __name__, template_folder="../../templates")

upstream = cfg("cgit", "remote")

@cgit.route("/<user>/<repo>", defaults={ "cgit_path": "" })
@cgit.route("/<user>/<repo>/", defaults={ "cgit_path": "" })
@cgit.route("/<user>/<repo>/<path:cgit_path>")
def cgit_passthrough(user, repo, cgit_path):
    r = requests.get("{}/{}".format(upstream, request.full_path))
    return render_template("cgit.html", cgit_html=r.text)
