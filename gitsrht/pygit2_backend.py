import pygit2
import requests
from srht.config import get_origin

def str_to_libgit2_object_type(otype):
    return {
        "commit": pygit2.GIT_OBJ_COMMIT,
        "tree": pygit2.GIT_OBJ_TREE,
        "blob": pygit2.GIT_OBJ_BLOB,
        "tag": pygit2.GIT_OBJ_TAG,
    }[otype]

_gitsrht = get_origin("git.sr.ht")

class OdbBackend(pygit2.OdbBackend):
    def __init__(self, authorization, owner_name, repo_name,
            upstream=_gitsrht, session=None):
        super().__init__()
        self.base_url = f"{upstream}/api/{owner_name}/repos/{repo_name}"
        self.authorization = authorization
        if session == None:
            self.session = requests.Session()
        else:
            self.session = session

    def _get(self, path, *args, **kwargs):
        headers = kwargs.pop("headers", dict())
        return self.session.get(f"{self.base_url}{path}",
                headers={**self.authorization, **headers})

    def _head(self, path, *args, **kwargs):
        headers = kwargs.pop("headers", dict())
        return self.session.head(f"{self.base_url}{path}",
                headers={**self.authorization, **headers})

    def exists(self, oid):
        r = self._head(f"/lookup/{str(oid)}")
        return r.status_code != 404

    def exists_prefix(self, oid_prefix):
        r = self._get(f"/lookup/{str(oid_prefix)}")
        if r.status_code == 404:
            raise KeyError(r.text)
        elif r.status_code == 409:
            raise ValueError(r.text)
        return r.text

    def read(self, oid):
        r = self._get(f"/odb/{str(oid)}")
        if r.status_code == 404:
            raise KeyError(r.text)
        elif r.status_code == 409:
            raise ValueError(r.text)
        otype = r.headers["X-Git-Object-Type"]
        otype = str_to_libgit2_object_type(otype)
        return otype, r.content

    def read_header(self, oid):
        r = self._head(f"/odb/{str(oid)}")
        if r.status_code == 404:
            raise KeyError(r.text)
        elif r.status_code == 409:
            raise ValueError(r.text)
        otype = r.headers["X-Git-Object-Type"]
        otype = str_to_libgit2_object_type(otype)
        length = int(r.headers["Content-Length"])
        return otype, length

    def read_prefix(self, oid_prefix):
        oid = self.exists_prefix(oid_prefix)
        return (oid, *self.read(oid))

    def __iter__(self):
        raise NotImplementedError()

    def refresh(self):
        pass # no-op

class RefdbBackend(pygit2.RefdbBackend):
    def __init__(self, authorization, owner_name, repo_name,
            upstream=_gitsrht, session=None):
        super().__init__()
        self.base_url = f"{upstream}/api/{owner_name}/repos/{repo_name}"
        self.authorization = authorization
        if session == None:
            self.session = requests.Session()
        else:
            self.session = session

    def _get(self, path, *args, **kwargs):
        headers = kwargs.pop("headers", dict())
        return self.session.get(f"{self.base_url}{path}",
                headers={**self.authorization, **headers})

    def _head(self, path, *args, **kwargs):
        headers = kwargs.pop("headers", dict())
        return self.session.head(f"{self.base_url}{path}",
                headers={**self.authorization, **headers})

    def exists(self, ref):
        r = self._head(f"/refdb/{ref}")
        if r.status_code == 404:
            return False
        elif r.status_code == 200:
            return True
        else:
            raise Exception(r.text)

    def lookup(self, ref):
        r = self._get(f"/refdb/{ref}")
        if r.status_code == 404:
            raise KeyError(r.text)
        elif r.status_code != 200:
            raise Exception(r.text)
        if " " in r.text:
            target, peel = r.text.split(" ", 1)
            return pygit2.Reference(ref, target, peel)
        else:
            return pygit2.Reference(ref, r.text)

    def write(self, ref, force, who, message, old, old_target):
        raise NotImplementedError()

    def rename(self, old_name, new_name, force, who, message):
        raise NotImplementedError()

    def delete(self, ref_name, old_id, old_target):
        raise NotImplementedError()

    def has_log(self, ref_name):
        raise NotImplementedError()

    def ensure_log(self, ref_name):
        raise NotImplementedError()

    def __iter__(self):
        raise NotImplementedError()

    def __next__(self):
        raise NotImplementedError()

class GitSrhtRepository(pygit2.Repository):
    """
    A pygit2.Repository which is backed by the git.sr.ht API rather than by
    local storage.
    """
    def __init__(self, authorization, owner_name, repo_name, upstream=_gitsrht):
        """
        authorization: a dictionary of headers providing API authorization
        (e.g. from srht.api.get_authorization)

        owner_name: the canonical name of the repository owner
        """
        super().__init__()
        self.session = requests.Session()
        odb = pygit2.Odb()
        odb_backend = OdbBackend(authorization, owner_name, repo_name,
                upstream=upstream, session=self.session)
        odb.add_backend(odb_backend, 1)
        refdb = pygit2.Refdb.new(self)
        refdb_backend = RefdbBackend(authorization, owner_name, repo_name,
                upstream=upstream, session=self.session)
        refdb.set_backend(refdb_backend)
        self.set_odb(odb)
        self.set_refdb(refdb)
