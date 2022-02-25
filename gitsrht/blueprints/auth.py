import os
from flask import Blueprint, request
from gitsrht.access import get_repo, has_access, UserAccess
from urllib.parse import urlparse, unquote

auth = Blueprint("auth", __name__)

@auth.route("/authorize")
def authorize_http_access():
    original_uri = request.headers.get("X-Original-URI")
    original_uri = urlparse(original_uri)
    path = unquote(original_uri.path)
    original_path = os.path.normpath(path).split('/')
    if len(original_path) < 3:
        return "authorized", 200
    owner, repo = original_path[1], original_path[2]
    owner, repo = get_repo(owner, repo)
    if not repo:
        return "unauthorized", 403
    if not has_access(repo, UserAccess.read):
        return "unauthorized", 403
    return "authorized", 200
