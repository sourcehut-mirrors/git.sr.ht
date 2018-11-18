import binascii
import os
import pygit2
import pygments
import sys
import subprocess
from datetime import datetime, timedelta
from jinja2 import Markup
from flask import Blueprint, render_template, abort, send_file, request
from flask import Response, redirect, url_for
from flask_login import current_user
from gitsrht.access import get_repo, has_access, UserAccess
from gitsrht.editorconfig import EditorConfig
from gitsrht.redis import redis
from gitsrht.git import Repository as GitRepository, commit_time, annotate_tree
from gitsrht.git import diffstat
from gitsrht.types import User, Repository, Redirect
from gitsrht.rss import generate_feed
from io import BytesIO
from pygments import highlight
from pygments.lexers import guess_lexer_for_filename, TextLexer
from pygments.formatters import HtmlFormatter
from srht.config import cfg
from srht.markdown import markdown

repo = Blueprint('repo', __name__)

@repo.route("/authorize")
def authorize_http_access():
    original_uri = request.headers.get("X-Original-URI")
    original_uri = original_uri.split("/")
    owner, repo = original_uri[1], original_uri[2]
    owner, repo = get_repo(owner, repo)
    if not repo:
        return "authorized", 200
    if not has_access(repo, UserAccess.read):
        return "unauthorized", 403
    return "authorized", 200

def get_readme(repo, tip):
    if not tip or not "README.md" in tip.tree:
        return None
    readme = tip.tree["README.md"]
    if readme.type != "blob":
        return None
    key = f"git.sr.ht:git:markdown:{readme.id.hex}:v3"
    html = redis.get(key)
    if html:
        return Markup(html.decode())
    try:
        md = repo.get(readme.id).data.decode()
    except:
        pass
    html = markdown(md, ["h1", "h2", "h3", "h4", "h5"])
    redis.setex(key, html, timedelta(days=7))
    return Markup(html)

def _highlight_file(name, data, blob_id):
    key = f"git.sr.ht:git:highlight:{blob_id}"
    html = redis.get(key)
    if html:
        return Markup(html.decode())
    try:
        lexer = guess_lexer_for_filename(name, data)
    except pygments.util.ClassNotFound:
        lexer = TextLexer()
    formatter = HtmlFormatter()
    style = formatter.get_style_defs('.highlight')
    html = f"<style>{style}</style>" + highlight(data, lexer, formatter)
    redis.setex(key, html, timedelta(days=7))
    return Markup(html)

def get_repo_or_redir(owner, repo):
    owner, repo = get_repo(owner, repo)
    if not repo:
        abort(404)
    if not has_access(repo, UserAccess.read):
        abort(401)
    if isinstance(repo, Redirect):
        view_args = request.view_args
        if not "repo" in view_args or not "owner" in view_args:
            return redirect(url_for(".summary",
                owner=repo.new_repo.owner.canonical_name,
                repo=repo.new_repo.name))
        view_args["owner"] = repo.new_repo.owner.canonical_name
        view_args["repo"] = repo.new_repo.name
        abort(redirect(url_for(request.endpoint, **view_args)))
    return owner, repo

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
        base = (cfg("git.sr.ht", "origin")
            .replace("http://", "")
            .replace("https://", ""))
        clone_urls = [
            url.format(base, owner.canonical_name, repo.name)
            for url in ["https://{}/{}/{}", "git@{}:{}/{}"]
        ]
        if git_repo.is_empty:
            return render_template("empty-repo.html", owner=owner, repo=repo,
                    clone_urls=clone_urls)
        default_branch = git_repo.default_branch()
        tip = git_repo.get(default_branch.target)
        commits = get_last_3_commits(tip)
        readme = get_readme(git_repo, tip)
        tags = [(ref, git_repo.get(git_repo.references[ref].target))
            for ref in git_repo.listall_references()
            if ref.startswith("refs/tags/")]
        tags = sorted(tags, key=lambda c: commit_time(c[1]), reverse=True)
        latest_tag = tags[0] if len(tags) else None
        return render_template("summary.html", view="summary",
                owner=owner, repo=repo, readme=readme, commits=commits,
                clone_urls=clone_urls, latest_tag=latest_tag,
                default_branch=default_branch)

def lookup_ref(git_repo, ref):
    ref = ref or git_repo.default_branch().name[len("refs/heads/"):]
    try:
        commit = git_repo.revparse_single(ref)
    except KeyError:
        abort(404)
    except ValueError:
        abort(404)
    if isinstance(commit, pygit2.Tag):
        commit = git_repo.get(commit.target)
    return commit, ref

@repo.route("/<owner>/<repo>/tree", defaults={"ref": None, "path": ""})
@repo.route("/<owner>/<repo>/tree/<ref>", defaults={"path": ""})
@repo.route("/<owner>/<repo>/tree/<ref>/<path:path>")
def tree(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref = lookup_ref(git_repo, ref)

        tree = commit.tree
        if not tree:
            abort(404)
        editorconfig = EditorConfig(git_repo, tree, path)

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
                data = None
                if not blob.is_binary:
                    try:
                        data = blob.data.decode()
                    except:
                        data = '[unable to decode]'
                return render_template("blob.html", view="tree",
                        owner=owner, repo=repo, ref=ref, path=path, entry=entry,
                        blob=blob, data=data, commit=commit,
                        highlight_file=_highlight_file,
                        editorconfig=editorconfig)
            tree = git_repo.get(entry.id)

        tree = annotate_tree(git_repo, tree, commit)
        tree = sorted(tree, key=lambda e: e.name)

        return render_template("tree.html", view="tree", owner=owner, repo=repo,
                ref=ref, commit=commit, tree=tree, path=path)

@repo.route("/<owner>/<repo>/blob/<ref>/<path:path>")
def raw_blob(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref = lookup_ref(git_repo, ref)

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

@repo.route("/<owner>/<repo>/archive/<ref>.tar.gz")
def archive(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref = lookup_ref(git_repo, ref)

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
            else:
                self.commit = repo.get(self.tag.target)
        else:
            self.type = None

def collect_refs(git_repo):
    refs = {}
    for _ref in git_repo.references:
        _ref = _AnnotatedRef(git_repo, git_repo.references[_ref])
        if not _ref.type:
            continue
        if _ref.commit.id.hex not in refs:
            refs[_ref.commit.id.hex] = []
        refs[_ref.commit.id.hex].append(_ref)
    return refs

def get_log(git_repo, commit, commits_per_page=20):
    commits = list()
    for commit in git_repo.walk(commit.id, pygit2.GIT_SORT_TIME):
        commits.append(commit)
        if len(commits) >= commits_per_page + 1:
            break

    return commits

@repo.route("/<owner>/<repo>/log", defaults={"ref": None, "path": ""})
@repo.route("/<owner>/<repo>/log/<ref>", defaults={"path": ""})
@repo.route("/<owner>/<repo>/log/<ref>/<path:path>")
def log(owner, repo, ref, path):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref = lookup_ref(git_repo, ref)
        refs = collect_refs(git_repo)

        from_id = request.args.get("from")
        if from_id:
            commit = git_repo.get(from_id)

        commits = get_log(git_repo, commit)

        return render_template("log.html", view="log",
                owner=owner, repo=repo, ref=ref, path=path,
                commits=commits, refs=refs)


@repo.route("/<owner>/<repo>/log/rss.xml", defaults={"ref": None})
@repo.route("/<owner>/<repo>/log/<ref>/rss.xml")
def log_rss(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref = lookup_ref(git_repo, ref)
        commits = get_log(git_repo, commit)

    repo_name = f"{repo.owner.canonical_name}/{repo.name}"
    title = f"{repo_name} log"
    description = f"Git log for {repo_name} {ref}"
    link = cfg("git.sr.ht", "origin") + url_for("repo.log",
        owner=repo.owner.canonical_name,
        repo=repo.name,
        ref=ref if ref != "master" else None).replace("%7E", "~")  # hack

    return generate_feed(repo, commits, title, link, description)

@repo.route("/<owner>/<repo>/commit/<ref>")
def commit(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref = lookup_ref(git_repo, ref)
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

@repo.route("/<owner>/<repo>/commit/<ref>.patch")
def patch(owner, repo, ref):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        commit, ref = lookup_ref(git_repo, ref)
        try:
            commit = git_repo.revparse_single(ref)
        except KeyError:
            abort(404)
        if isinstance(commit, pygit2.Tag):
            ref = git_repo.get(commit.target)
        subp = subprocess.run([
            "git",
            "--git-dir", repo.path,
            "format-patch",
            "--stdout", "-1",
            ref
        ], timeout=10, stdout=subprocess.PIPE, stderr=sys.stderr)
        if subp.returncode != 0:
            return "Error preparing patch", 500
        return Response(subp.stdout, mimetype='text/plain')

@repo.route("/<owner>/<repo>/refs")
def refs(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        tags = [(
                ref,
                git_repo.get(git_repo.references[ref].target)
            ) for ref in git_repo.references if ref.startswith("refs/tags/")]
        def _tag_key(tag):
            if isinstance(tag[1], pygit2.Commit):
                return tag[1].commit_time
            return tag[1].tagger.time
        tags = sorted(tags, key=_tag_key, reverse=True)
        branches = [(
                branch,
                git_repo.branches[branch],
                git_repo.get(git_repo.branches[branch].target)
            ) for branch in git_repo.branches]
        branches = sorted(branches, key=lambda b: b[2].commit_time, reverse=True)

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
    title = f"{repo_name} log"
    description = f"Git refs for {repo_name}"
    link = cfg("git.sr.ht", "origin") + url_for("repo.refs",
        owner=repo.owner.canonical_name,
        repo=repo.name).replace("%7E", "~")  # hack

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
