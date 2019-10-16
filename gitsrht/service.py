from gitsrht.types import User, OAuthToken, SSHKey
from scmsrht.service import BaseScmOAuthService, make_webhooks_notify_blueprint

class GitOAuthService(BaseScmOAuthService):
    def __init__(self):
        super().__init__("git.sr.ht", OAuthToken, User, SSHKey)

oauth_service = GitOAuthService()

webhooks_notify = make_webhooks_notify_blueprint(__name__, oauth_service)
