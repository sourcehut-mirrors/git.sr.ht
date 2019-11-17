import binascii
import json
import os
import pygit2
import pygments
import subprocess
import sys
from datetime import timedelta
from flask import Blueprint, render_template, abort, send_file, request
from flask import Response, url_for, session
from gitsrht.annotations import AnnotatedFormatter
from gitsrht.editorconfig import EditorConfig
from gitsrht.git import Repository as GitRepository, commit_time, annotate_tree
from gitsrht.git import diffstat, get_log
from gitsrht.rss import generate_feed
from io import BytesIO
from jinja2 import Markup
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import guess_lexer, guess_lexer_for_filename, TextLexer
from scmsrht.access import get_repo, get_repo_or_redir
from scmsrht.formatting import get_formatted_readme, get_highlighted_file
from scmsrht.redis import redis
from scmsrht.urls import get_clone_urls
from srht.config import cfg
from srht.markdown import markdown

repo = Blueprint('repo', __name__)

def get_readme(repo, tip, link_prefix=None):
    if not tip:
        return None

    def file_finder(name):
        try:
            blob = tip.tree[name]
        except KeyError:
            return None, None

        if blob and blob.type == "blob":
            return blob.id.hex, blob
        return None, None

    def content_getter(blob):
        return repo.get(blob.id).data.decode()

    return get_formatted_readme("git.sr.ht:git", file_finder, content_getter,
            link_prefix=link_prefix)

def _highlight_file(repo, ref, name, data, blob_id):
    def get_annos():
        annotations = redis.get(f"git.sr.ht:git:annotations:{repo.id}:{blob_id}")
        if annotations:
            return json.loads(annotations.decode())
        return None
    link_prefix = url_for(
        'repo.tree', owner=repo.owner, repo=repo.name, ref=ref)
    return get_highlighted_file("git.sr.ht:git", name, blob_id, data,
            formatter=AnnotatedFormatter(get_annos, link_prefix))

def render_empty_repo(owner, repo):
    origin = cfg("git.sr.ht", "origin")
    urls = get_clone_urls(origin, owner, repo, 'git@{origin}:{user}/{repo}')
    return render_template("empty-repo.html", owner=owner, repo=repo,
            clone_urls=urls)

def get_last_3_commits(commit):
    commits = [commit]
    for parent in commit.parents:
        commits.append(parent)
        for grandparent in parent.parents:
            commits.append(grandparent)

    commits = sorted(commits, key=lambda c: commit_time(c), reverse=True)
    return commits[:3]

@repo.route("/<owner>/<repo>")
def summary(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)

    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return render_empty_repo(owner, repo)

        default_branch = git_repo.default_branch()
        tip = git_repo.get(default_branch.target)
        commits = get_last_3_commits(tip)
        link_prefix = url_for(
            'repo.tree', owner=repo.owner, repo=repo.name,
            ref=default_branch.name)
        readme = get_readme(git_repo, tip,
            link_prefix=link_prefix)
        tags = [(ref, git_repo.get(git_repo.references[ref].target))
            for ref in git_repo.listall_references()
            if ref.startswith("refs/tags/")]
        tags = [tag for tag in tags
                if isinstance(tag[1], pygit2.Tag) or isinstance(tag[1], pygit2.Commit)]
        tags = sorted(tags, key=lambda c: commit_time(c[1]), reverse=True)
        latest_tag = tags[0] if len(tags) else None

        message = session.pop("message", None)
        return render_template("summary.html", view="summary",
                owner=owner, repo=repo, readme=readme, commits=commits,
                latest_tag=latest_tag, default_branch=default_branch,
                is_annotated=lambda t: isinstance(t, pygit2.Tag),
                message=message)

def lookup_ref(git_repo, ref, path):
    ref = ref or git_repo.default_branch().name[len("refs/heads/"):]
    if path is None:
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
    return commit, ref, "/".join(path)

@repo.route("/<owner>/<repo>/tree", defaults={"ref": None, "path": ""})
@repo.route("/<owner>/<repo>/tree/<path:ref>", defaults={"path": ""})
@repo.route("/<owner>/<repo>/tree/<ref>/<path:path>")
def tree(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        if git_repo.is_empty:
            return render_empty_repo(owner, repo)

        commit, ref, path = lookup_ref(git_repo, ref, path)

        tree = commit.tree
        if not tree:
            abort(404)
        editorconfig = EditorConfig(git_repo, tree, path)

        path = path.split("/")
        for part in path:
            if part == "":
                continue
            if not tree or part not in tree:
                abort(404)
            entry = tree[part]
            if entry.type == "blob":
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
                return render_template("blob.html", view="blob",
                        owner=owner, repo=repo, ref=ref, path=path, entry=entry,
                        blob=blob, data=data, commit=commit,
                        highlight_file=_highlight_file,
                        editorconfig=editorconfig)
            tree = git_repo.get(entry.id)

        if not tree:
            abort(404)
        tree = annotate_tree(git_repo, tree, commit)
        tree = sorted(tree, key=lambda e: e.name)

        return render_template("tree.html", view="tree", owner=owner, repo=repo,
                ref=ref, commit=commit, tree=tree, path=path)

@repo.route("/<owner>/<repo>/blob/<path:ref>/<path:path>")
def raw_blob(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, path = lookup_ref(git_repo, ref, path)

        blob = None
        entry = None
        tree = commit.tree
        path = path.split("/")
        for part in path:
            if part == "":
                continue
            if part not in tree:
                abort(404)
            entry = tree[part]
            if entry.type == "blob":
                tree = annotate_tree(git_repo, tree, commit)
                commit = next(e.commit for e in tree if e.name == entry.name)
                blob = git_repo.get(entry.id)
                break
            tree = git_repo.get(entry.id)

        if not blob:
            abort(404)

        return send_file(BytesIO(blob.data),
                as_attachment=blob.is_binary,
                attachment_filename=entry.name,
                mimetype="text/plain" if not blob.is_binary else None)

@repo.route("/<owner>/<repo>/archive/<path:ref>.tar.gz")
def archive(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)

        path = f"/tmp/{commit.id.hex}{binascii.hexlify(os.urandom(8))}.tar.gz"
        try:
            args = [
                "git",
                "--git-dir", repo.path,
                "archive",
                "--format=tar.gz",
                "--prefix", f"{repo.name}-{ref}/",
                "-o", path, ref
            ]
            subp = subprocess.run(args, timeout=30,
                    stdout=sys.stdout, stderr=sys.stderr)
        except:
            try:
                os.unlink(path)
            except:
                pass
            raise

        if subp.returncode != 0:
            try:
                os.unlink(path)
            except:
                pass
            return "Error preparing archive", 500

        f = open(path, "rb")
        os.unlink(path)
        return send_file(f, mimetype="application/tar+gzip", as_attachment=True,
                attachment_filename=f"{repo.name}-{ref}.tar.gz")

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
        refs = collect_refs(git_repo)

        from_id = request.args.get("from")
        if from_id:
            try:
                commit = git_repo.get(from_id)
            except ValueError:
                abort(404)

        commits = get_log(git_repo, commit)

        return render_template("log.html", view="log",
                owner=owner, repo=repo, ref=ref, path=path,
                commits=commits, refs=refs)


@repo.route("/<owner>/<repo>/log/rss.xml", defaults={"ref": None})
@repo.route("/<owner>/<repo>/log/<path:ref>/rss.xml")
def log_rss(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)
        commits = get_log(git_repo, commit)

    repo_name = f"{repo.owner.canonical_name}/{repo.name}"
    title = f"{repo_name} log"
    description = f"Git log for {repo_name} {ref}"
    link = cfg("git.sr.ht", "origin") + url_for("repo.log",
        owner=repo.owner.canonical_name,
        repo=repo.name,
        ref=ref if ref != "master" else None)

    return generate_feed(repo, commits, title, link, description)

@repo.route("/<owner>/<repo>/commit/<path:ref>")
def commit(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)
        try:
            parent = git_repo.revparse_single(ref + "^")
            diff = git_repo.diff(parent, ref)
        except KeyError:
            parent = None
            diff = commit.tree.diff_to_tree(swap=True)
        diff.find_similar(pygit2.GIT_DIFF_FIND_RENAMES)
        refs = collect_refs(git_repo)
        return render_template("commit.html", view="log",
            owner=owner, repo=repo, ref=ref, refs=refs,
            commit=commit, parent=parent,
            diff=diff, diffstat=diffstat, pygit2=pygit2)

@repo.route("/<owner>/<repo>/commit/<path:ref>.patch")
def patch(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref, _ = lookup_ref(git_repo, ref, None)
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
        default_branch = git_repo.default_branch().name
        branches = sorted(branches,
                key=lambda b: (b[1].name == default_branch, b[2].commit_time),
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
                page=page + 1, total_pages=total_pages)


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
        return render_template("ref.html", view="refs",
                owner=owner, repo=repo, git_repo=git_repo, tag=tag)
