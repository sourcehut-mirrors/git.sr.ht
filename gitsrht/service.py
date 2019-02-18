from flask import Blueprint, request, url_for
from gitsrht.types import User, OAuthToken, SSHKey
from srht.api import get_results
from srht.database import db
from srht.config import cfg
from srht.flask import csrf_bypass
from srht.oauth import AbstractOAuthService
import json
import requests

origin = cfg("git.sr.ht", "origin")
meta_origin = cfg("meta.sr.ht", "origin")
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

    def ensure_user_sshkey(self, user, meta_key):
        """
        Ensures this SSH key is registered with this user, and returns True if
        their authorized_keys file needs to be regenerated.

        `meta_key` should be the key object returned from meta.sr.ht.
        """
        key = SSHKey.query.filter(
                SSHKey.meta_id == meta_key["id"]).one_or_none()
        if key:
            return False
        key = SSHKey()
        key.user_id = user.id
        key.meta_id = meta_key["id"]
        key.key = meta_key["key"]
        key.fingerprint = meta_key["fingerprint"]
        db.session.add(key)
        return True

    def ensure_meta_webhooks(self, user, webhooks):
        webhook_url = origin + url_for("webhooks.notify.notify_keys")
        webhooks.update({
            webhook_url: ["ssh-key:add", "ssh-key:remove"]
        })
        return super().ensure_meta_webhooks(user, webhooks)

    def lookup_or_register(self, token, token_expires, scopes):
        user = super().lookup_or_register(token, token_expires, scopes)
        db.session.flush()
        keys_url = f"{meta_origin}/api/user/ssh-keys"
        for key in get_results(keys_url, user.oauth_token):
            self.ensure_user_sshkey(user, key)
        db.session.commit()
        return user

oauth_service = GitOAuthService()

webhooks_notify = Blueprint("webhooks.notify", __name__)

@csrf_bypass
@webhooks_notify.route("/webhook/notify/keys", methods=["POST"])
def notify_keys():
    payload = json.loads(request.data.decode('utf-8'))
    event = request.headers.get("X-Webhook-Event")
    # TODO: Regenerate authorized_keys
    if event == "ssh-key:add":
        user = User.query.filter(
                User.username == payload["owner"]["name"]).one_or_none()
        oauth_service.ensure_user_sshkey(user, payload)
        db.session.commit()
        return "Added user's SSH key, thanks!"
    elif event == "ssh-key:remove":
        key = SSHKey.query.filter(
                SSHKey.meta_id == payload["id"]).one_or_none()
        if key:
            db.session.delete(key)
            db.session.commit()
        return "Removed user's SSH key, thanks!"
    return f"Unexpected event {event}"
