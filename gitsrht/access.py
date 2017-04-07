from enum import IntFlag
from flask_login import current_user
from gitsrht.types import User, Repository, RepoVisibility

class UserAccess(IntFlag):
    none = 0
    read = 1
    write = 2
    manage = 4

def get_repo(owner_name, repo_name):
    if owner_name[0] == "~":
        user = User.query.filter(User.username == owner_name[1:]).first()
        if user:
            repo = Repository.query.filter(Repository.owner_id == user.id)\
                .filter(Repository.name == repo_name).first()
        else:
            repo = None
        return user, repo
    else:
        # TODO: organizations
        return None, None

def get_access(repo, user=None):
    if not user:
        user = current_user
    # TODO: ACLs
    if not repo:
        return UserAccess.none
    if not current_user:
        if repo.visibility == RepoVisibility.public or \
                repo.visibility == RepoVisibility.unlisted:
            return UserAccess.read
    if repo.owner_id == current_user.id:
        return UserAccess.read | UserAccess.write | UserAccess.manage
    if repo.visibility == RepoVisibility.private:
        return UserAccess.none
    return UserAccess.read

def has_access(repo, access, user=None):
    if not user:
        user = current_user
    return access in get_access(repo, user)

def check_access(owner_name, repo_name, access):
    owner, repo = get_repo(owner_name, repo_name)
    if not owner or not repo:
        abort(404)
    a = get_access(repo)
    if not UserAccess.write in a:
        abort(404)
    if not access in a:
        abort(403)
    return owner, repo
