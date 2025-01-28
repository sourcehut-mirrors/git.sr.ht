from srht.config import cfg
from srht.oauth import AbstractOAuthService, DelegatedScope
from gitsrht.types import User, OAuthToken

client_id = cfg("git.sr.ht", "oauth-client-id")
client_secret = cfg("git.sr.ht", "oauth-client-secret")
builds_client_id = cfg("builds.sr.ht", "oauth-client-id", default=None)

class GitOAuthService(AbstractOAuthService):
    def __init__(self):
        super().__init__("git.sr.ht", OAuthToken, User)

        required_scopes = ["profile", "keys"] + ([
                "{}/jobs:write".format(builds_client_id)
            ] if builds_client_id else [])

        super().__init__(client_id, client_secret,
                required_scopes=required_scopes, delegated_scopes=[
                    DelegatedScope("info", "repository details", True),
                    DelegatedScope("data", "version controlled data", False),
                    DelegatedScope("access", "access control lists", True),
                ], user_class=User, token_class=OAuthToken)

oauth_service = GitOAuthService()
