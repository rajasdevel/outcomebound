"""The two lifecycle signals `adopt --detect` reads from Git and the version files, and the
drift lines `adopt --check` and `--detect` print where the files contradict the install's record.

What this module decides: how many distinct people wrote the recent history (authors counted by
email, bots and automation left out, never a name or an address kept); whether the project has a
release identity (a tag, or a version file); and which lines say that a signal is present while
the recorded fragment selection, or the exposure line of the project's `local` fragment, says
otherwise. Each line is `<signal> present, record says <what>`.

What it does not decide: whether a line is right (a person reads it), or any exit code: a drift
line refuses nothing. It reads files and runs read-only Git commands; it writes nothing.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from pathlib import Path

from outcomebound_tools import discovery, facts, fragments

# "Recent" is the last 100 commits of the current branch that are not merges. A count, not a
# date: a project that was quiet for a year still shows who maintains it, and a busy one shows
# who works on it now. Merges are left out because a merge commit names whoever pressed the button.
WINDOW = 100
RELEASE_TAGS = "version-like git tags"
VERSION_FILE = "VERSION"
CODEOWNERS = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
TEAM, SOLO, DEPLOY, CI_RELEASE = "team", "solo", "deploy", "ci-release"

# An author is a bot or automation when the name or address holds `[bot]`, or the part of the
# address before `@` is a no-reply mailbox, or is `bot`, or ends in `-bot`, `_bot` or `.bot`. The
# separator is required: a person's mailbox can end in the letters `bot` (Talbot). A person's
# private GitHub address, `<id>+<login>@users.noreply.github.com`, is neither: its part before
# `@` holds the login.
_NO_REPLY = re.compile(r"^(no-?reply|do-?not-?reply)$")
_BOT_MAILBOX = re.compile(r"(^|[-_.])bot$")
_ACT = re.compile(r" (runs|uses) (.+)$")
# A version: `1.2`, `1.2.3`, `v1.2.3`, with a pre-release or build suffix (`1.2.3-rc.1`).
_NUMBER = r"\d+\.\d+(\.\d+)*([-+][0-9A-Za-z.+-]+)?"
# A tag is a version bare (`v1.2.3`, `1.2.3`), or prefixed by a package or a module: `pkg@1.2.3`,
# `pkg-v1.2.3`, `sub/v1.2.3`, `release/1.2.3` (changesets, lerna, Go submodules).
_VERSION = re.compile(rf"^v?{_NUMBER}$")
_TAG = re.compile(
    rf"^(v?{_NUMBER}|\S+@v?{_NUMBER}|\S+-v{_NUMBER}|\S+/v{_NUMBER}|release/{_NUMBER})$"
)
_EXPOSURE = re.compile(r"Exposure\s+[—-]", re.IGNORECASE)
_NEXT_PART = re.compile(r"^(\*\*|[A-Z][A-Za-z ]*\s—\s)")
_MAINTAINED = re.compile(r"maintained\s+by\s*:\s*([^;\n]*)", re.IGNORECASE)
_NOTE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_ONE = re.compile(r"^\W*(one|1|a\s+single|single|sole|just\s+one|solo)\b", re.IGNORECASE)
# What, after the first words, names another maintainer or a group.
_MORE = re.compile(r",|&|\+|\b(and|or|plus|of\s+the|team|maintainers|people|developers)\b", re.I)
_ACKNOWLEDGED = re.compile(r"Drift\s*[—-]\s*([A-Za-z][A-Za-z-]*)\s*:")
SIGNAL_IDS = ("recent-authors", "codeowners", "deploy", "publishing", "exposure")
# What a declared edge names: publishing (a release tag, a package, a registry), or deploying
# (a deploy, a promotion, production).
_PUBLISH_EDGE = re.compile(r"\b(publish\w*|releas\w*|tag\w*|package\w*|registr\w*)", re.I)
_DEPLOY_EDGE = re.compile(r"\b(deploy\w*|promot\w*|production|prod)\b", re.I)
# A workflow that builds or pushes a container image.
_IMAGE = re.compile(
    r"docker/build-push-action|\bdocker\s+(buildx\s+)?(push|build\w*\s[^\n]*--push)\b"
    r"|\bbuildx\b[^\n]*\bpush\b",
    re.I,
)


def _is_bot(name: str, email: str) -> bool:
    if "[bot]" in name.lower() or "[bot]" in email:
        return True
    mailbox = email.split("@", 1)[0]
    return bool(_NO_REPLY.match(mailbox) or _BOT_MAILBOX.search(mailbox))


def recent_authors(target: Path) -> int | None:
    """The people among the authors of the last `WINDOW` commits that are not merges on the
    current branch, after the project's `.mailmap`, bots and automation left out. Two identities
    that share a name or an email, lower-cased, are one person: one person often commits under two
    emails with one name. None where Git cannot read a history (no commit yet, or no Git)."""

    output = discovery.git_read(
        target, "log", f"--max-count={WINDOW}", "--no-merges", "--format=%aE%x1f%aN"
    )
    if output is None or not output.strip():
        return None
    parent: dict[str, str] = {}

    def root(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    emails: set[str] = set()
    for line in output.decode("utf-8", "replace").splitlines():
        email, _, name = line.partition("\x1f")
        email, name = email.strip().lower(), name.strip().lower()
        if not email or _is_bot(name, email):
            continue
        emails.add(email)
        if name:
            parent[root("email:" + email)] = root("name:" + name)
    return len({root("email:" + email) for email in emails})


def release_identity(target: Path) -> list[str]:
    """The evidence of a release practice, in a fixed order: a tag that is a version (`v1.2.3`,
    `1.2.3`, `v1.2`, or one with a prefix such as `pkg@1.2.3`), and a `VERSION` file whose first
    line is a version. A version in
    `pyproject.toml`, `package.json` or `Cargo.toml` is no evidence, since nearly every package
    carries one. Empty where there is none."""

    found: list[str] = []
    tags = discovery.git_read(target, "tag", "--list")
    names = [] if tags is None else tags.decode("utf-8", "replace").splitlines()
    if any(_TAG.match(name.strip()) for name in names):
        found.append(RELEASE_TAGS)
    text, _ = facts.read_small(target, VERSION_FILE)
    first = (text or "").strip().splitlines()[:1]
    if first and _VERSION.match(first[0].strip()):
        found.append(VERSION_FILE)
    return found


def signals(target: Path) -> list[facts.Signal]:
    """The recent-authors and release-identity signals, for `--detect`'s signal lines. A signal
    says something that can change a proposal: recent authors only from two (one author is the
    ordinary case), release identity only from a version tag or a `VERSION` file."""

    found: list[facts.Signal] = []
    authors = recent_authors(target)
    if authors is not None and authors >= 2:
        where = f"git log, the last {WINDOW} commits without merges, bots left out"
        found.append(facts.Signal("recent-authors", where, str(authors), "Context"))
    evidence = release_identity(target)
    if evidence:
        found.append(facts.Signal("release-identity", ", ".join(evidence), "", "Distinguish"))
    return found


# What a publishing-workflow signal's act (`job <job> runs <command>` or `job <job> uses
# <action>`) publishes: a package or a release (`ci-release`), or a service (`deploy`). Any other
# act, `docker push` among them, is neither: it names no fragment.
_PACKAGE_COMMANDS = frozenset(
    {
        "npm publish",
        "pnpm publish",
        "yarn npm publish",
        "twine upload",
        "uv publish",
        "cargo publish",
        "gh release create",
        "goreleaser release",
    }
)
_PACKAGE_ACTIONS = frozenset(
    {
        "pypa/gh-action-pypi-publish",
        "js-devtools/npm-publish",
        "rubygems/release-gem",
        "softprops/action-gh-release",
        "ncipollo/release-action",
        "helm/chart-releaser-action",
        "goreleaser/goreleaser-action",
    }
)
_DEPLOY_COMMANDS = frozenset(
    {
        "terraform apply",
        "kubectl apply",
        "helm upgrade",
        "fly deploy",
        "flyctl deploy",
        "wrangler deploy",
        "firebase deploy",
    }
)
_DEPLOY_ACTIONS = frozenset(
    {
        "actions/deploy-pages",
        "peaceiris/actions-gh-pages",
        "cloudflare/wrangler-action",
        "azure/webapps-deploy",
        "google-github-actions/deploy-cloudrun",
        "aws-actions/amazon-ecs-deploy-task-definition",
        "firebaseextended/action-hosting-deploy",
    }
)


def _acts(files: Sequence[facts.CiFile]) -> list[tuple[str, str, str]]:
    """Each act of the publishing-workflow signals as (the workflow file, `runs` or `uses`, the
    command or action)."""

    found = []
    for item in facts.workflow_signals(files):
        match = _ACT.search(item.value) if item.kind == "publishing-workflow" else None
        if match is not None:
            found.append((item.where, match.group(1), match.group(2).strip().lower()))
    return found


def _is_package(how: str, what: str) -> bool:
    return (how == "runs" and what in _PACKAGE_COMMANDS) or (
        how == "uses" and what in _PACKAGE_ACTIONS
    )


def _is_deploy(how: str, what: str) -> bool:
    return (how == "runs" and what in _DEPLOY_COMMANDS) or (
        how == "uses" and what in _DEPLOY_ACTIONS
    )


def _only_pushes_image(item: facts.CiFile) -> bool:
    """Whether a workflow builds or pushes a container image: with no package publish in it
    (`_publishes_package` has settled that), an image is neither a package nor a release."""

    text = (item.data or b"").decode("utf-8", "replace")
    return _IMAGE.search(text) is not None


def _publishes_package(files: Sequence[facts.CiFile]) -> bool:
    """Whether `--detect` recognises the publishing of a package or a release: a step that
    runs a package publish or uses a package publishing action; or a workflow file whose name
    starts with `release` or `publish`, as the `ci-release` fragment detects, unless its steps
    deploy a service and publish nothing, or only build or push a container image, where the
    name is no evidence. A name with steps that show none of these is evidence alone."""

    acts = _acts(files)
    if any(_is_package(how, what) for _, how, what in acts):
        return True
    for item in files:
        if not item.path.startswith(f"{facts.WORKFLOWS}/"):
            continue
        if not Path(item.path).name.startswith(("release", "publish")):
            continue
        deploys = any(path == item.path and _is_deploy(how, what) for path, how, what in acts)
        if not deploys and not _only_pushes_image(item):
            return True
    return False


def _deploys_in_workflow(files: Sequence[facts.CiFile]) -> bool:
    """Whether a workflow step deploys a service, by a command or action of the signal's list."""

    return any(_is_deploy(how, what) for _, how, what in _acts(files))


def _has_codeowners(target: Path) -> bool:
    return any((target / name).is_file() for name in CODEOWNERS)


def _says_one(value: str) -> bool:
    """Whether a `maintained by:` value names one person: it starts with one, a single, sole or
    solo, and nothing after names another. A note in parentheses or brackets is passed over, and
    `with agents` is allowed; `and`, a comma, `of the`, `team` or `maintainers` is not."""

    text = re.split(r"\.(\s|$)", _NOTE.sub(" ", value))[0].strip()
    start = _ONE.match(text)
    return start is not None and _MORE.search(text[start.end() :]) is None


def maintained_by_one(local_text: str) -> bool:
    """Whether every `Exposure —` line of the `local` fragment says one person maintains the
    project (one line for each stream). Lenient: no such line, a line without the
    `maintained by:` fact, or a value that is not one person reads False."""

    lines = local_text.splitlines()
    verdicts: list[bool] = []
    for index, line in enumerate(lines):
        found = _EXPOSURE.search(line)
        if found is None:
            continue
        parts = [line[found.start() :]]
        for following in lines[index + 1 :]:
            if not following.strip() or _NEXT_PART.match(following):
                break
            parts.append(following.strip())
        match = _MAINTAINED.search(" ".join(parts))
        verdicts.append(match is not None and _says_one(match.group(1)))
    return bool(verdicts) and all(verdicts)


def acknowledged(local_text: str | None) -> set[str]:
    """The signals a person settled with a `Drift — <signal>: <reason>` line in the `local`
    fragment; an id outside `SIGNAL_IDS` is ignored."""

    found = _ACKNOWLEDGED.findall(local_text or "")
    return {name.lower() for name in found} & set(SIGNAL_IDS)


def declared_edges(local_text: str | None) -> str:
    """The edges the `local` fragment declares, one string; empty where it is not readable."""

    if local_text is None:
        return ""
    try:
        return "\n".join(fragments.parse_fragment(local_text, "local").edges)
    except fragments.FragmentError:
        return ""


def lines(
    target: Path,
    selected: Collection[str],
    detected: Collection[str],
    files: Sequence[facts.CiFile],
    local_text: str | None,
) -> list[str]:
    """The drift lines, one for each signal the files show that the record contradicts.
    `selected` is the fragment selection the manifest records, `detected` the fragment ids
    `--detect` proposes from the files, `local_text` the `local` fragment's text where the
    record selects it. A signal prints nothing where a person settled it with a `Drift —` line,
    where an edge the `local` fragment declares already names the act (publishing for
    `ci-release`, deploying for `deploy`), or where the record agrees."""

    found: list[str] = []
    settled = acknowledged(local_text)
    edges = declared_edges(local_text)
    authors = recent_authors(target) or 0
    if SOLO in selected and authors >= 2 and "recent-authors" not in settled:
        found.append(f"{authors} recent authors present, record says solo selected")
    claims = ((TEAM not in selected, "team not selected"), (SOLO in selected, "solo selected"))
    said = [phrase for held, phrase in claims if held]
    if said and _has_codeowners(target) and "codeowners" not in settled:
        found.append(f"CODEOWNERS present, record says {' and '.join(said)}")
    deploys = DEPLOY in detected or _deploys_in_workflow(files)
    if (
        deploys
        and DEPLOY not in selected
        and "deploy" not in settled
        and _DEPLOY_EDGE.search(edges) is None
    ):
        found.append("deploy configuration present, record says deploy not selected")
    if (
        _publishes_package(files)
        and CI_RELEASE not in selected
        and "publishing" not in settled
        and _PUBLISH_EDGE.search(edges) is None
    ):
        found.append("publishing workflow present, record says ci-release not selected")
    if (
        authors >= 2
        and "exposure" not in settled
        and local_text is not None
        and maintained_by_one(local_text)
    ):
        found.append(
            f"{authors} recent authors present, record says the local Exposure line is "
            "maintained by one person"
        )
    return found
