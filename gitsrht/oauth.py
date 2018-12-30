from srht.config import cfg
from srht.oauth import AbstractOAuthService
from gitsrht.types import OAuthToken, User

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
