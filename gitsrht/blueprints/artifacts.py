import requests
from flask import Blueprint, redirect, render_template, request
from flask import send_file, abort, url_for
from gitsrht.git import Repository as GitRepository, strip_pgp_signature
from gitsrht.access import check_access, UserAccess
from srht.crypto import encrypt_request_authorization
from srht.graphql import exec_gql, GraphQLUpload, GraphQLError, Error
from srht.oauth import loginrequired
from srht.validation import Validation

artifacts = Blueprint('artifacts', __name__)

@artifacts.route("/<owner>/<repo>/refs/upload/<path:ref>", methods=["POST"])
@loginrequired
def ref_upload(owner, repo, ref):
    owner, repo = check_access(owner, repo, UserAccess.manage)
    with GitRepository(repo.path) as git_repo:
        valid = Validation(request)
        valid.expect(request.files.get("file"), "File is required", field="file")
        file_list = request.files.getlist("file")
        default_branch = git_repo.default_branch()
        if not valid.ok:
            return render_template("ref.html", view="refs",
                    owner=owner, repo=repo, git_repo=git_repo, tag=ref,
                    strip_pgp_signature=strip_pgp_signature,
                    default_branch=default_branch, **valid.kwargs)
        for f in file_list:
            exec_gql("git.sr.ht", """
                mutation UploadArtifact(
                    $repoID: Int!,
                    $revspec: String!,
                    $file: Upload!,
                ) {
                    uploadArtifact(repoId: $repoID, revspec: $revspec, file: $file) {
                        id
                    }
                }
                """,
                repoID=repo.id,
                revspec=f"refs/tags/{ref}",
                file=GraphQLUpload(f.filename, f, "application/octet-stream"),
                valid=valid)
            if not valid.ok:
                return render_template("ref.html", view="refs",
                        owner=owner, repo=repo, git_repo=git_repo, tag=ref,
                        strip_pgp_signature=strip_pgp_signature,
                        default_branch=default_branch, **valid.kwargs)
        return redirect(url_for("repo.ref",
            owner=owner.canonical_name,
            repo=repo.name,
            ref=ref))

@artifacts.route("/<owner>/<repo>/refs/download/<path:ref>/<filename>")
def ref_download(owner, repo, ref, filename):
    owner, repo = check_access(owner, repo, UserAccess.read)

    params = {
        "owner": owner.username,
        "repo": repo.name,
        "ref": f"refs/tags/{ref}",
        "filename": filename,
    }

    try:
        r = exec_gql("git.sr.ht", """
        query GetArtifactURL(
            $owner: String!,
            $repo: String!,
            $ref: String!,
            $filename: String!,
        ) {
            user(username: $owner) {
                repository(name: $repo) {
                    reference(name: $ref) {
                        artifact(filename: $filename) {
                            filename
                            url
                        }
                    }
                }
            }
        }
        """, user=owner, **params)
    except GraphQLError as err:
        if err.has(Error.NOT_FOUND):
            abort(404)
        raise

    ref = r["user"]["repository"]["reference"]
    if ref is None:
        abort(404)
    artifact = ref["artifact"]
    if artifact is None:
        abort(404)

    url = artifact["url"]
    auth = encrypt_request_authorization(user=owner)
    resp = requests.get(url, headers=auth, stream=True)
    return send_file(resp.raw,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=artifact["filename"])

@artifacts.route("/~<owner>/<repo>/refs/delete/<path:ref>/<filename>", methods=["POST"])
@loginrequired
def ref_delete(owner, repo, ref, filename):
    check_access("~" + owner, repo, UserAccess.manage)

    params = {
        "owner": owner,
        "repo": repo,
        "ref": f"refs/tags/{ref}",
        "filename": filename,
    }
    try:
        r = exec_gql("git.sr.ht", """
        query GetArtifact(
            $owner: String!,
            $repo: String!,
            $ref: String!,
            $filename: String!,
        ) {
            user(username: $owner) {
                repository(name: $repo) {
                    reference(name: $ref) {
                        artifact(filename: $filename) {
                            id
                        }
                    }
                }
            }
        }
        """, **params)
    except GraphQLError as err:
        if err.has(Error.NOT_FOUND):
            abort(404)
        raise

    artifact = r["user"]["repository"]["reference"]["artifact"]
    exec_gql("git.sr.ht", """
    mutation DeleteArtifact($id: Int!) {
        deleteArtifact(id: $id) {
            id
        }
    }
    """, id=artifact["id"])

    return redirect(url_for("repo.ref",
        owner="~" + owner, repo=repo, ref=ref))
