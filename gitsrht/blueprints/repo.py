import binascii
import json
import os
import pygit2
import pygments
import subprocess
import sys
from datetime import timedelta
from flask import Blueprint, render_template, abort, current_app, send_file, request
from flask import Response, url_for, session, redirect
from gitsrht.editorconfig import EditorConfig
from gitsrht.git import Repository as GitRepository, commit_time, annotate_tree
from gitsrht.git import diffstat, get_log, diff_for_commit
from gitsrht.rss import generate_feed
from gitsrht.types import Artifact
from io import BytesIO
from jinja2 import Markup
from jinja2.utils import url_quote, escape
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import guess_lexer, guess_lexer_for_filename, TextLexer
from scmsrht.access import get_repo, get_repo_or_redir
from scmsrht.formatting import get_formatted_readme, get_highlighted_file
from scmsrht.urls import get_clone_urls
from srht.config import cfg, get_origin
from srht.markdown import markdown, sanitize
from urllib.parse import urlparse

repo = Blueprint('repo', __name__)

def get_readme(repo, git_repo, tip, link_prefix=None):
    if repo.readme is not None:
        return Markup(sanitize(repo.readme))

    if not tip:
        return None

    def file_finder(name):
        try:
            blob = tip.tree[name]
        except KeyError:
            return None, None

        if blob:
            btype = (blob.type_str
                    if hasattr(blob, "type_str") else blob.type)
            if btype == "blob":
                return blob.id.hex, blob
        return None, None

    def content_getter(blob):
        return git_repo.get(blob.id).data.decode()

    return get_formatted_readme("git.sr.ht:git", file_finder, content_getter,
            link_prefix=link_prefix)

def _highlight_file(repo, ref, entry, data, blob_id, commit_id):
    link_prefix = url_for('repo.tree', owner=repo.owner,
            repo=repo.name, ref=ref)
    if entry.filemode == pygit2.GIT_FILEMODE_LINK:
        return Markup("<div class=\"highlight\"><pre>" +
                f"<a href=\"{url_quote(data.encode('utf-8'))}\">" +
                f"{escape(data)}</a><pre></div>")
    else:
        return get_highlighted_file("git.sr.ht:git", entry.name, blob_id, data)

def render_empty_repo(owner, repo):
    origin = cfg("git.sr.ht", "origin")
    git_user = cfg("git.sr.ht::dispatch", "/usr/bin/gitsrht-keys", "git:git").split(":")[0]
    urls = get_clone_urls(origin, owner, repo, git_user + '@{origin}:{user}/{repo}')
    return render_template("empty-repo.html", owner=owner, repo=repo,
            clone_urls=urls)

def get_last_3_commits(git_repo, commit):
    commits = list()
    for c in git_repo.walk(commit.id, pygit2.GIT_SORT_TOPOLOGICAL):
        commits.append(c)
        if len(commits) >= 3:
            break
    return commits

@repo.route("/<owner>/<repo>")
def summary(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)

    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return render_empty_repo(owner, repo)

        default_branch = git_repo.default_branch()
        if not default_branch:
            return render_empty_repo(owner, repo)

        tip = git_repo.get(default_branch.target)
        commits = get_last_3_commits(git_repo, tip)
        link_prefix = url_for(
            'repo.tree', owner=repo.owner, repo=repo.name,
            ref=f"{default_branch.name}/")  # Trailing slash needed
        blob_prefix = url_for(
            'repo.raw_blob', owner=repo.owner, repo=repo.name,
            ref=f"{default_branch.name}/", path="")  # Trailing slash needed
        readme = get_readme(repo, git_repo, tip,
            link_prefix=[link_prefix, blob_prefix])
        tags = [(ref, git_repo.get(git_repo.references[ref].target))
            for ref in git_repo.listall_references()
            if ref.startswith("refs/tags/")]
        tags = [tag for tag in tags
                if isinstance(tag[1], pygit2.Tag) or isinstance(tag[1], pygit2.Commit)]
        tags = sorted(tags, key=lambda c: commit_time(c[1]), reverse=True)
        latest_tag = tags[0] if len(tags) else None

        license = False
        for path in [
                "LICENSE", "LICENCE", "COPYING",
                "LICENSE.txt", "license.txt",
                "LICENCE.txt", "licence.txt",
                "COPYING.txt", "copying.txt",
                "COPYRIGHT.txt", "copyright.txt",
                "LICENSE.md", "license.md",
                "LICENCE.md", "licence.md",
                "COPYING.md", "copying.md",
                "COPYRIGHT.md", "copyright.md",
                "COPYRIGHT", "copyright",
                "LICENSES", "licenses",
                "LICENCES", "licences",
        ]:
            if path in tip.tree:
                license = True
                break

        message = session.pop("message", None)
        return render_template("summary.html", view="summary",
                owner=owner, repo=repo, readme=readme, commits=commits,
                latest_tag=latest_tag, default_branch=default_branch,
                is_annotated=lambda t: isinstance(t, pygit2.Tag),
                message=message, license=license)

@repo.route("/<owner>/<repo>/<path:path>")
def go_get(owner, repo, path):
    if "go-get" not in request.args:
        abort(404)
    owner, repo = get_repo_or_redir(owner, repo)
    root = get_origin("git.sr.ht", external=True)
    origin = urlparse(root).netloc
    return "".join(['<!doctype html>',
        '<title>Placeholder page for Go import resolution</title>',
        '<meta name="go-import" content="',
            f'{origin}/{owner.canonical_name}/{repo.name} ',
            f'git ',
            f'{root}/{owner.canonical_name}/{repo.name}',
        '" />',
    ])

def lookup_ref(git_repo, ref, path):
    branch = git_repo.default_branch()
    if not branch:
        abort(404)
    ref = ref or branch.name[len("refs/heads/"):]
    if not path:
        path = []
    else:
        path = path.split("/")
    commit = None
    try:
        commit = git_repo.revparse_single(ref)
    except KeyError:
        pass
    except ValueError:
        pass
    while commit is None and len(path):
        ref += "/" + path[0]
        path = path[1:]
        try:
            commit = git_repo.revparse_single(ref)
        except KeyError:
            pass
        except ValueError:
            pass
    if commit is None:
        abort(404)
    if isinstance(commit, pygit2.Tag):
        commit = git_repo.get(commit.target)
    if not commit:
        abort(404)
    return commit, ref, "/".join(path)

@repo.route("/<owner>/<repo>/tree", defaults={"ref": None, "path": ""})
@repo.route("/<owner>/<repo>/tree/<path:ref>", defaults={"path": ""})
@repo.route("/<owner>/<repo>/tree/<ref>/<path:path>")
def tree(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)

    if ref and "/" in ref:
        ref, _, path = ref.partition("/")

    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return render_empty_repo(owner, repo)

        # lookup_ref will cycle through the path to separate
        # the actual ref from the actual path
        commit, ref, path = lookup_ref(git_repo, ref, path)
        if isinstance(commit, pygit2.Tag):
            commit = git_repo.get(commit.target)
        orig_commit = commit
        if not isinstance(commit, pygit2.Commit):
            abort(404)
        tree = commit.tree
        if not tree:
            abort(404)
        editorconfig = EditorConfig(git_repo, tree, path)

        entry = tree
        path = path.split("/")
        for part in path:
            if part == "":
                continue
            if not tree or part not in tree:
                abort(404)
            entry = tree[part]
            etype = (entry.type_str
                    if hasattr(entry, "type_str") else entry.type)
            if etype == "blob":
                tree = annotate_tree(git_repo, tree, commit)
                commit = next(
                        (e.commit for e in tree if e.name == entry.name), None)
                blob = git_repo.get(entry.id)
                data = None
                if not blob.is_binary:
                    try:
                        data = blob.data.decode()
                    except:
                        data = '[unable to decode]'
                md = not blob.is_binary and entry.name.endswith(".md")
                if md:
                    link_prefix = url_for('repo.tree', owner=repo.owner,
                            repo=repo.name, ref=ref,
                            path=os.path.dirname("/".join(path)))
                    blob_prefix = url_for(
                        'repo.raw_blob', owner=repo.owner, repo=repo.name,
                        ref=ref, path=os.path.dirname("/".join(path)))
                    md = markdown(data,
                            link_prefix=[link_prefix, blob_prefix])
                force_source = "view-source" in request.args
                return render_template("blob.html", view="blob",
                        owner=owner, repo=repo, ref=ref, path=path, entry=entry,
                        blob=blob, data=data, commit=orig_commit,
                        highlight_file=_highlight_file,
                        editorconfig=editorconfig,
                        markdown=md, force_source=force_source, pygit2=pygit2)
            tree = git_repo.get(entry.id)

        if not tree:
            abort(404)
        tree = annotate_tree(git_repo, tree, commit)
        tree = sorted(tree, key=lambda e: e.name)

        return render_template("tree.html", view="tree", owner=owner, repo=repo,
                ref=ref, commit=commit, entry=entry, tree=tree, path=path,
                pygit2=pygit2)

def resolve_blob(git_repo, ref, path):
    commit, ref, path = lookup_ref(git_repo, ref, path)
    if not isinstance(commit, pygit2.Commit):
        abort(404)

    blob = None
    entry = None
    tree = commit.tree
    orig_commit = commit
    path = path.split("/")
    for part in path:
        if part == "":
            continue
        if part not in tree:
            abort(404)
        entry = tree[part]
        etype = (entry.type_str
                if hasattr(entry, "type_str") else entry.type)
        if etype == "blob":
            tree = annotate_tree(git_repo, tree, commit)
            commit = next(e.commit for e in tree if e.name == entry.name)
            blob = git_repo.get(entry.id)
            break
        tree = git_repo.get(entry.id)

    if not blob:
        abort(404)

    return orig_commit, ref, path, blob, entry

@repo.route("/<owner>/<repo>/blob/<path:ref>/<path:path>")
def raw_blob(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        orig_commit, ref, path, blob, entry = resolve_blob(git_repo, ref, path)

        return send_file(BytesIO(blob.data),
                as_attachment=blob.is_binary,
                attachment_filename=entry.name,
                mimetype="text/plain" if not blob.is_binary else None)

def _lookup_user(email, cache):
    if email not in cache:
        cache[email] = current_app.lookup_user(email)
    return cache[email]

def lookup_user():
    cache = {}
    return lambda email: _lookup_user(email, cache)

@repo.route("/<owner>/<repo>/blame/<path:ref>", defaults={"path": ""})
@repo.route("/<owner>/<repo>/blame/<ref>/<path:path>")
def blame(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        orig_commit, ref, path, blob, entry = resolve_blob(git_repo, ref, path)
        if blob.is_binary:
            return redirect(url_for("repo.log",
                owner=repo.owner.canonical_name, repo=repo.name, ref=ref,
                path="/".join(path)))
        try:
            data = blob.data.decode()
        except:
            return redirect(url_for("repo.log",
                owner=repo.owner.canonical_name, repo=repo.name, ref=ref,
                path="/".join(path)))

        try:
            blame = git_repo.blame("/".join(path), newest_commit=orig_commit.oid)
        except KeyError as ke:  # Path not in the tree
            abort(404)
        except ValueError:
            # ValueError: object at path 'hubsrht/' is not of the asked-for type 3
            abort(400)

        return render_template("blame.html", view="blame", owner=owner,
                repo=repo, ref=ref, path=path, entry=entry, blob=blob, data=data,
                blame=blame, commit=orig_commit, highlight_file=_highlight_file,
                editorconfig=EditorConfig(git_repo, orig_commit.tree, path),
                lookup_user=lookup_user(), pygit2=pygit2)

@repo.route("/<owner>/<repo>/archive/<path:ref>.tar.gz")
def archive(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)
        if not isinstance(commit, pygit2.Commit):
            abort(404)

        args = [
            "git",
            "--git-dir", repo.path,
            "archive",
            "--format=tar.gz",
            "--prefix", f"{repo.name}-{ref}/",
            ref
        ]
        subp = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=sys.stderr)

        return send_file(subp.stdout, mimetype="application/tar+gzip",
                as_attachment=True, attachment_filename=f"{repo.name}-{ref}.tar.gz")

class _AnnotatedRef:
    def __init__(self, repo, ref):
        self.ref = ref
        self.target = ref.target
        if ref.name.startswith("refs/heads/"):
            self.type = "branch"
            self.name = ref.name[len("refs/heads/"):]
            self.branch = repo.get(ref.target)
            self.commit = self.branch
        elif ref.name.startswith("refs/tags/"):
            self.type = "tag"
            self.name = ref.name[len("refs/tags/"):]
            self.tag = repo.get(self.target)
            if isinstance(self.tag, pygit2.Commit):
                self.commit = self.tag
            elif isinstance(self.tag, pygit2.Tag):
                self.commit = repo.get(self.tag.target)
        else:
            self.type = None

def collect_refs(git_repo):
    refs = {}
    for _ref in git_repo.references:
        _ref = _AnnotatedRef(git_repo, git_repo.references[_ref])
        if not _ref.type or not hasattr(_ref, "commit"):
            continue
        if _ref.commit.id.hex not in refs:
            refs[_ref.commit.id.hex] = []
        refs[_ref.commit.id.hex].append(_ref)
    return refs

@repo.route("/<owner>/<repo>/log", defaults={"ref": None, "path": ""})
@repo.route("/<owner>/<repo>/log/<path:ref>", defaults={"path": ""})
@repo.route("/<owner>/<repo>/log/<ref>/<path:path>")
def log(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return render_empty_repo(owner, repo)

        commit, ref, path = lookup_ref(git_repo, ref, path)
        if not isinstance(commit, pygit2.Commit):
            abort(404)
        refs = collect_refs(git_repo)

        from_id = request.args.get("from")
        if from_id:
            try:
                commit = git_repo.get(from_id)
            except ValueError:
                abort(404)
        if not commit:
            abort(404)

        commits = get_log(git_repo, commit, path)

        entry = None
        if path and commit.tree and path in commit.tree:
            entry = commit.tree[path]

        return render_template("log.html", view="log",
                owner=owner, repo=repo, ref=ref, path=path.split("/"),
                commits=commits, refs=refs, entry=entry, pygit2=pygit2)


@repo.route("/<owner>/<repo>/log/rss.xml", defaults={"ref": None})
@repo.route("/<owner>/<repo>/log/<path:ref>/rss.xml")
def log_rss(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)
        if not isinstance(commit, pygit2.Commit):
            abort(404)
        commits = get_log(git_repo, commit)
        default_branch = git_repo.default_branch_name()

    repo_name = f"{repo.owner.canonical_name}/{repo.name}"
    title = f"{repo_name} log"
    description = f"Git log for {repo_name} {ref}"
    link = cfg("git.sr.ht", "origin") + url_for("repo.log",
        owner=repo.owner.canonical_name,
        repo=repo.name,
        ref=ref if ref != default_branch else None)

    return generate_feed(repo, commits, title, link, description)

@repo.route("/<owner>/<repo>/commit/<path:ref>")
def commit(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)
        if not isinstance(commit, pygit2.Commit):
            abort(404)
        parent, diff = diff_for_commit(git_repo, commit)
        refs = collect_refs(git_repo)
        return render_template("commit.html", view="log",
            owner=owner, repo=repo, ref=ref, refs=refs,
            commit=commit, parent=parent,
            diff=diff, diffstat=diffstat, pygit2=pygit2,
            default_branch=git_repo.default_branch())

@repo.route("/<owner>/<repo>/commit/<path:ref>.patch")
def patch(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)
        if not isinstance(commit, pygit2.Commit):
            abort(404)
        try:
            commit = git_repo.revparse_single(ref)
        except KeyError:
            abort(404)
        if isinstance(commit, pygit2.Tag):
            ref = git_repo.get(commit.target)
        try:
            subp = subprocess.run([
                "git",
                "--git-dir", repo.path,
                "format-patch",
                "--stdout", "-1",
                ref
            ], timeout=10, stdout=subprocess.PIPE, stderr=sys.stderr)
        except subprocess.TimeoutExpired:
            return "Operation timed out", 500
        if subp.returncode != 0:
            return "Error preparing patch", 500
        return Response(subp.stdout, mimetype='text/plain')

@repo.route("/<owner>/<repo>/refs")
def refs(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return render_empty_repo(owner, repo)

        tags = [(
                ref,
                git_repo.get(git_repo.references[ref].target)
            ) for ref in git_repo.references if ref.startswith("refs/tags/")]
        tags = [tag for tag in tags
                if isinstance(tag[1], pygit2.Commit) or isinstance(tag[1], pygit2.Tag)]
        def _tag_key(tag):
            if isinstance(tag[1], pygit2.Commit):
                return tag[1].commit_time
            return tag[1].tagger.time
        tags = sorted(tags, key=_tag_key, reverse=True)
        branches = [(
                branch,
                git_repo.branches[branch],
                git_repo.get(git_repo.branches[branch].target)
            ) for branch in git_repo.branches.local]
        default_branch = git_repo.default_branch()
        branches = sorted(branches,
                key=lambda b: (b[1].name == default_branch.name, b[2].commit_time),
                reverse=True)

        results_per_page = 10
        page = request.args.get("page")
        total_results = len(tags)
        total_pages = total_results // results_per_page + 1
        if total_results % results_per_page == 0:
            total_pages -= 1
        if page is not None:
            try:
                page = int(page) - 1
                tags = tags[page*results_per_page:page*results_per_page+results_per_page]
            except:
                page = 0
        else:
            page = 0
            tags = tags[:results_per_page]

        return render_template("refs.html", view="refs",
                owner=owner, repo=repo, tags=tags, branches=branches,
                git_repo=git_repo, isinstance=isinstance, pygit2=pygit2,
                page=page + 1, total_pages=total_pages,
                default_branch=default_branch)


@repo.route("/<owner>/<repo>/refs/rss.xml")
def refs_rss(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        references = [
            git_repo.references[name]
            for name in git_repo.references
            if name.startswith("refs/tags/")
        ]

    def _ref_sort_key(ref):
        target = git_repo.get(ref.target)
        author = target.author if hasattr(target, 'author') else target.tagger
        return author.time + author.offset

    references = sorted(references, key=_ref_sort_key, reverse=True)[:20]

    repo_name = f"{repo.owner.canonical_name}/{repo.name}"
    title = f"{repo_name} refs"
    description = f"Git refs for {repo_name}"
    link = cfg("git.sr.ht", "origin") + url_for("repo.refs",
        owner=repo.owner.canonical_name, repo=repo.name)

    return generate_feed(repo, references, title, link, description)

@repo.route("/<owner>/<repo>/refs/<ref>")
def ref(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        try:
            tag = git_repo.revparse_single(ref)
        except KeyError:
            abort(404)
        except ValueError:
            abort(404)
        if isinstance(tag, pygit2.Commit):
            return redirect(url_for(".commit",
                owner=owner, repo=repo.name, ref=tag.id.hex))
        artifacts = (Artifact.query
                .filter(Artifact.user_id == repo.owner_id)
                .filter(Artifact.repo_id == repo.id)
                .filter(Artifact.commit == tag.target.hex)).all()
        return render_template("ref.html", view="refs",
                owner=owner, repo=repo, git_repo=git_repo, tag=tag,
                artifacts=artifacts, default_branch=git_repo.default_branch())
