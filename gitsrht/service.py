from flask import Blueprint, request, url_for
from gitsrht.types import User, OAuthToken
from srht.api import get_results
from srht.config import cfg
from srht.flask import csrf_bypass
from srht.oauth import AbstractOAuthService
import json
import requests

origin = cfg("git.sr.ht", "origin")
client_id = cfg("git.sr.ht", "oauth-client-id")
client_secret = cfg("git.sr.ht", "oauth-client-secret")
builds_client_id = cfg("builds.sr.ht", "oauth-client-id", default=None)

class GitOAuthService(AbstractOAuthService):
    def __init__(self):
        super().__init__(client_id, client_secret,
                required_scopes=["profile", "keys"] + ([
                    "{}/jobs:write".format(builds_client_id)
                ] if builds_client_id else []),
                token_class=OAuthToken, user_class=User)

    def ensure_meta_webhooks(self, user, webhooks):
        webhook_url = origin + url_for("webhooks.notify.notify_keys")
        webhooks.update({
            webhook_url: ["ssh-key:add", "ssh-key:remove"]
        })
        super().ensure_meta_webhooks(user, webhooks)

webhooks_notify = Blueprint("webhooks.notify", __name__)

@csrf_bypass
@webhooks_notify.route("/webhook/notify/keys", methods=["POST"])
def notify_keys():
    payload = json.loads(request.data.decode('utf-8'))
    event = request.headers.get("X-Webhook-Event")
    # TODO: Store these keys in the database
    print(event, payload)
    return "Thanks!"
