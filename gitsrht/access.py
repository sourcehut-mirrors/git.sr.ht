from flask import abort
from datetime import datetime
from enum import IntFlag
from flask_login import current_user
from gitsrht.types import User, Repository, RepoVisibility, Redirect
from gitsrht.types import Access, AccessMode
from srht.database import db

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
        if user and not repo:
            repo = (Redirect.query
                    .filter(Redirect.owner_id == user.id)
                    .filter(Redirect.name == repo_name)
                ).first()
        return user, repo
    else:
        # TODO: organizations
        return None, None

def get_access(repo, user=None):
    if not user:
        user = current_user
    if not repo:
        return UserAccess.none
    if isinstance(repo, Redirect):
        # Just pretend they have full access for long enough to do the redirect
        return UserAccess.read | UserAccess.write | UserAccess.manage
    if not user:
        if repo.visibility == RepoVisibility.public or \
                repo.visibility == RepoVisibility.unlisted:
            return UserAccess.read
        return UserAccess.none
    if repo.owner_id == user.id:
        return UserAccess.read | UserAccess.write | UserAccess.manage
    acl = Access.query.filter(Access.repo_id == repo.id).first()
    if acl:
        acl.updated = datetime.utcnow()
        db.session.commit()
        if acl.mode == AccessMode.ro:
            return UserAccess.read
        else:
            return UserAccess.read | UserAccess.write
    if repo.visibility == RepoVisibility.private:
        return UserAccess.none
    return UserAccess.read

def has_access(repo, access, user=None):
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
