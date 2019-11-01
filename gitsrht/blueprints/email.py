import email
import mailbox
import pygit2
import re
import smtplib
import subprocess
import sys
from email.policy import SMTPUTF8
from email.utils import make_msgid, parseaddr
from flask import Blueprint, render_template, abort, request, url_for, session
from flask import redirect
from gitsrht.git import Repository as GitRepository, commit_time, diffstat
from gitsrht.git import get_log
from scmsrht.access import get_repo_or_redir
from srht.config import cfg, cfgi, cfgb
from srht.flask import loginrequired, current_user
from srht.validation import Validation
from tempfile import NamedTemporaryFile
from textwrap import TextWrapper

mail = Blueprint('mail', __name__)

smtp_host = cfg("mail", "smtp-host", default=None)
smtp_port = cfgi("mail", "smtp-port", default=None)
smtp_user = cfg("mail", "smtp-user", default=None)
smtp_password = cfg("mail", "smtp-password", default=None)
smtp_from = cfg("mail", "smtp-from", default=None)

@mail.route("/<owner>/<repo>/send-email")
@loginrequired
def send_email_start(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        ncommits = int(request.args.get("commits", default=8))
        if ncommits > 32:
            ncommits = 32
        if ncommits < 8:
            ncommits = 8
        selected_branch = request.args.get("branch", default=None)

        branches = [(
                branch,
                git_repo.branches[branch],
                git_repo.get(git_repo.branches[branch].target)
            ) for branch in git_repo.branches.local]
        default_branch = git_repo.default_branch().name
        branches = sorted(branches,
                key=lambda b: (b[0] == selected_branch, commit_time(b[2])),
                reverse=True)

        commits = dict()
        for branch in branches[:2]:
            commits[branch[0]] = get_log(git_repo,
                    branch[2], commits_per_page=ncommits)

        return render_template("send-email.html",
                view="send-email", owner=owner, repo=repo,
                selected_branch=selected_branch, branches=branches,
                commits=commits)

@mail.route("/<owner>/<repo>/send-email/end", methods=["POST"])
@loginrequired
def send_email_end(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        valid = Validation(request)
        branch = valid.require("branch")
        commit = valid.require(f"commit-{branch}")

        branch = git_repo.branches[branch]
        tip = git_repo.get(branch.target)
        start = git_repo.get(commit)

        log = get_log(git_repo, tip, until=start)
        diffs = list()
        for commit in log:
            try:
                parent = git_repo.revparse_single(commit.oid.hex + "^")
                diff = git_repo.diff(parent, commit)
            except KeyError:
                parent = None
                diff = commit.tree.diff_to_tree(swap=True)
            diff.find_similar(pygit2.GIT_DIFF_FIND_RENAMES)
            diffs.append(diff)

        return render_template("send-email-end.html",
                view="send-email", owner=owner, repo=repo,
                commits=log, start=start, diffs=diffs,
                diffstat=diffstat)

commentary_re = re.compile(r"""
---\n
(?P<context>
    (\ .*\ +\|\ +\d+\ [-+]+\n)+
    \ \d+\ files?\ changed,.*\n
    \n
    diff\ --git
)
""", re.MULTILINE | re.VERBOSE)

def prepare_patchset(repo, git_repo, cover_letter=None, extra_headers=False,
        to=None, cc=None):
    with NamedTemporaryFile() as ntf:
        wrapper = TextWrapper(
                expand_tabs=False,
                replace_whitespace=False,
                width=72,
                drop_whitespace=True,
                break_long_words=False)

        valid = Validation(request)
        start_commit = valid.require("start_commit")
        end_commit = valid.require("end_commit")
        cover_letter_subject = valid.optional("cover_letter_subject")
        if cover_letter is None:
            cover_letter = valid.optional("cover_letter")
        if not valid.ok:
            return None

        outgoing_domain = cfg("git.sr.ht", "outgoing-domain")
        args = [
            "git",
            "--git-dir", repo.path,
            "-c", f"user.name=~{current_user.username}",
            "-c", f"user.email={current_user.username}@{outgoing_domain}",
            "format-patch",
            f"--from=~{current_user.username} <{current_user.username}@{outgoing_domain}>",
            f"--subject-prefix=PATCH {repo.name}",
            "--stdout",
        ]
        if cover_letter:
            args += ["--cover-letter"]
        args += [f"{start_commit}^..{end_commit}"]
        print(args)
        p = subprocess.run(args, timeout=30,
                stdout=subprocess.PIPE, stderr=sys.stderr)
        if p.returncode != 0:
            abort(400) # TODO: Something more useful, I suppose.

        ntf.write(p.stdout)
        ntf.flush()

        policy = SMTPUTF8.clone(max_line_length=998)
        factory = lambda f: email.message_from_bytes(f.read(), policy=policy)
        mbox = mailbox.mbox(ntf.name)
        emails = list(mbox)

        if cover_letter:
            subject = emails[0]["Subject"]
            del emails[0]["Subject"]
            emails[0]["Subject"] = (subject
                    .replace("*** SUBJECT HERE ***", cover_letter_subject))
            body = emails[0].get_payload(decode=True).decode()
            cover_letter = "\n".join(wrapper.wrap(cover_letter))
            body = body.replace("*** BLURB HERE ***", cover_letter)
            emails[0].set_payload(body)

        for i, email in enumerate(emails[(1 if cover_letter else 0):]):
            commentary = valid.optional(f"commentary_{i}")
            if not commentary:
                commentary = session.get(f"commentary_{i}")
            if not commentary:
                continue
            commentary = "\n".join(wrapper.wrap(commentary))
            body = email.get_payload(decode=True).decode()
            body = commentary_re.sub(r"---\n" + commentary.replace(
                "\\", r"\\") + r"\n\n\g<context>", body, count=1)
            email.set_payload(body)

        if extra_headers:
            msgid = make_msgid().split("@")
            for i, email in enumerate(emails):
                email["Message-ID"] = f"{msgid[0]}-{i}@{msgid[1]}"
                email["X-Mailer"] = "git.sr.ht"
                email["Reply-to"] = (f"{current_user.canonical_name} " +
                    f"<{current_user.email}>")
                if i != 0:
                    email["In-Reply-To"] = f"{msgid[0]}-{0}@{msgid[1]}"
                if to:
                    email["To"] = to
                if cc:
                    email["Cc"] = cc

        return emails

@mail.route("/<owner>/<repo>/send-email/review", methods=["POST"])
@loginrequired
def send_email_review(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        valid = Validation(request)
        start_commit = valid.require("start_commit")
        end_commit = valid.require("end_commit")
        cover_letter = valid.optional("cover_letter")
        cover_letter_subject = valid.optional("cover_letter_subject")
        if cover_letter and not cover_letter_subject:
            valid.error("Cover letter subject is required.",
                    field="cover_letter_subject")
        if cover_letter_subject and not cover_letter:
            valid.error("Cover letter body is required.", field="cover_letter")

        default_branch = git_repo.default_branch()
        tip = git_repo.get(default_branch.target)
        readme = None
        if "README.md" in tip.tree:
            readme = "README.md"
        elif "README" in tip.tree:
            readme = "README"

        emails = prepare_patchset(repo, git_repo)
        if not emails or not valid.ok:
            tip = git_repo.get(end_commit)
            start = git_repo.get(start_commit)

            log = get_log(git_repo, tip, until=start)
            diffs = list()
            for commit in log:
                try:
                    parent = git_repo.revparse_single(commit.oid.hex + "^")
                    diff = git_repo.diff(parent, commit)
                except KeyError:
                    parent = None
                    diff = commit.tree.diff_to_tree(swap=True)
                diff.find_similar(pygit2.GIT_DIFF_FIND_RENAMES)
                diffs.append(diff)

            return render_template("send-email-end.html",
                    view="send-email", owner=owner, repo=repo,
                    commits=log, start=start, diffs=diffs,
                    diffstat=diffstat, **valid.kwargs)

        for i, email in enumerate(emails):
            comm = valid.optional(f"commentary_{i}")
            if comm:
                session[f"commentary_{i}"] = comm

        session["cover_letter"] = cover_letter
        return render_template("send-email-review.html",
                view="send-email", owner=owner, repo=repo,
                readme=readme, emails=emails,
                start=git_repo.get(start_commit),
                end=git_repo.get(end_commit),
                cover_letter=bool(cover_letter),
                cover_letter_subject=cover_letter_subject)

@mail.route("/<owner>/<repo>/send-email/send", methods=["POST"])
@loginrequired
def send_email_send(owner, repo):
    owner, repo = get_repo_or_redir(owner, repo)
    with GitRepository(repo.path) as git_repo:
        valid = Validation(request)
        start_commit = valid.require("start_commit")
        end_commit = valid.require("end_commit")
        cover_letter_subject = valid.optional("cover_letter_subject")

        to = valid.require("patchset_to", friendly_name="To")
        cc = valid.optional("patchset_cc")
        recipients = list()

        if to:
            to_recipients = [parseaddr(r)[1] for r in to.split(",")]
            valid.expect('' not in to_recipients,
                    "Invalid recipient.", field="patchset_to")
            recipients += to_recipients
        if cc:
            cc_recipients = [parseaddr(r)[1] for r in cc.split(",")]
            valid.expect('' not in cc_recipients,
                    "Invalid recipient.", field="patchset_cc")
            recipients += cc_recipients

        if not valid.ok:
            cover_letter = session.get("cover_letter")
            emails = prepare_patchset(repo, git_repo, cover_letter=cover_letter)

            default_branch = git_repo.default_branch()
            tip = git_repo.get(default_branch.target)
            readme = None
            if "README.md" in tip.tree:
                readme = "README.md"
            elif "README" in tip.tree:
                readme = "README"

            return render_template("send-email-review.html",
                    view="send-email", owner=owner, repo=repo,
                    readme=readme, emails=emails,
                    start=git_repo.get(start_commit),
                    end=git_repo.get(end_commit),
                    cover_letter=bool(cover_letter),
                    **valid.kwargs)

        cover_letter = session.pop("cover_letter", None)
        emails = prepare_patchset(repo, git_repo,
                cover_letter=cover_letter, extra_headers=True,
                to=to, cc=cc)
        if not emails:
            abort(400) # Should work by this point

        # TODO: Send emails asyncronously
        smtp = smtplib.SMTP(smtp_host, smtp_port)
        smtp.ehlo()
        if smtp_user and smtp_password:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
        print("Sending to receipients", recipients)
        for i, email in enumerate(emails):
            session.pop("commentary_{i}", None)
            smtp.sendmail(smtp_user, recipients,
                    email.as_bytes(unixfrom=False))
        smtp.quit()

        # TODO: If we're connected to a lists.sr.ht address, link to their URL
        # in the archives.
        session["message"] = "Your patchset has been sent."
        return redirect(url_for('repo.summary',
            owner=repo.owner, repo=repo.name))
