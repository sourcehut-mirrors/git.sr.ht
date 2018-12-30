from srht.database import Base
from srht.oauth import ExternalUserMixin, ExternalOAuthTokenMixin

class User(Base, ExternalUserMixin):
    def __init__(*args, **kwargs):
        ExternalUserMixin.__init__(*args, **kwargs)

class OAuthToken(Base, ExternalOAuthTokenMixin):
    def __init__(*args, **kwargs):
        ExternalOAuthTokenMixin.__init__(*args, **kwargs)

from .repository import Repository, RepoVisibility
from .webhook import Webhook
from .redirect import Redirect
from .access import Access, AccessMode
