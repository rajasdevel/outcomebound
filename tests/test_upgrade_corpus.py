"""The upgrade corpus: a project that a released engine installed, in a shape that adopting
projects showed, is upgraded with this checkout's engine.

Each case builds a small synthetic Git project, installs it with a previous release's engine,
taken from this repository's tag by `git archive`, commits that install as an adopter would, adds
its shape, and then runs `adopt <project>` with the candidate engine, as the changelog's upgrade
step does. The shape comes after the previous install, so that one install for each release and
each set of install options serves every case that shares it, and so that a previous engine
that stops on the shape cannot keep the candidate from being tested.

The previous releases are two. `v1.0.0` is the oldest install that an adopter can hold, so it
has the most records, blocks and defaults to move. The release before the candidate is the one
that most adopters upgrade from: the newest tag at or below the candidate's `VERSION` that is not
the candidate itself. Between releases `VERSION` still names the previous release, so its tag is
that release; at a release `VERSION` names the release under test, and once its tag exists (the
tag's pipeline) that tag holds the candidate's own tree, so the tag before it is taken. A tag
that this clone does not hold (a shallow clone, a fork) skips with its name; CI fetches the whole
history, so it runs there.

The assertions are outcomes, not report bytes: `adopt --check` before the upgrade reads no
record `edited` that the project did not change, the upgrade does not stop and refuses nothing
that it must not (a block edited apart from its source is refused, as the negative control),
`adopt --check` reads every record current after it, the kinds of `warning` lines equal the
case's expected set, and nothing outside the install's own records changed: not the bytes of a
file, not `git status`, not the index.

`OB_UPGRADE_CANDIDATE` names another engine tree to upgrade with, such as `git archive` of an
older commit, so that a case can be shown to fail on the engine before the fix it guards. Every
canary finding becomes a case here, in the pull request that fixes it (docs/specs/README.md).
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from outcomebound_tools import adopt
from tests.portable import write

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git") or "git"
CANDIDATE = Path(os.environ.get("OB_UPGRADE_CANDIDATE") or ROOT).resolve()
OLDEST = "v1.0.0"
# Git converts line endings under `core.autocrlf=true`, which a Windows install of Git sets for
# every account: `git archive` then writes an earlier release's files with CRLF, which that
# release's engine cannot read (its tag holds no `.gitattributes`), and `git add` turns the
# bytes a case commits back to LF. This harness commits and archives exactly the bytes it names,
# so that a case that wants CRLF (`crlf_checkout`) writes it and an earlier release gets LF.
EXACT = ("-c", "core.autocrlf=false")
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")
# The scripts/outcomebound launcher's own run of a checkout, under this test's Python, so that
# every engine runs on the Python the suite runs on.
LAUNCH = """import runpy, sys
sys.path.insert(0, sys.argv[1])
sys.argv = ["outcomebound", *sys.argv[2:]]
runpy.run_module("outcomebound_tools", run_name="__main__", alter_sys=True)
"""
# What each case's previous install selects: both harnesses with a byte cap or a hook, the
# project's own local fragment, the workspace fragment (whose .agents/.gitignore ignores
# .agents/work/) and the tickets fragment, and a Done command.
INSTALL = (
    *("--harness", "claude-code,codex"),
    *("--fragments", "local,workspace,tickets"),
    *("--done", "true"),
)
# The pointers block then holds the local fragment and the skill lines only, so that an edit
# made to the fragment and to the block alike leaves the block as the candidate writes it.
LOCAL_ONLY = ("--harness", "claude-code,codex", "--fragments", "local", "--done", "true")
FINISH = (*INSTALL, "--finish-check")
# Past codex's byte cap, a session's instructions get a byte-cap warning.
CAP = adopt.harness_table(ROOT)["codex"]["doc_byte_cap"]
BLOCK = re.compile(
    r"<!-- outcomebound:begin id=(\S+) [^>]*-->.*?<!-- outcomebound:end id=\1 -->", re.DOTALL
)
# The stable start of each kind of `warning` line adopt prints; a line that matches none is its
# own kind, so a new warning fails the case that shows it, with its text.
KINDS = (
    (re.compile(r"(\S+): a session in "), "{}: a session in"),
    (re.compile(r"(\S+): a session here also loads "), "{}: a session here also loads"),
    (re.compile(r"tickets: the claim `"), "tickets: the claim"),
    (re.compile(r"tickets: the claims plan "), "tickets: the claims plan"),
    (re.compile(r".+: Git ignores it "), "Git ignores it"),
    (re.compile(r"AGENTS\.md holds changes that are not committed"), "AGENTS.md uncommitted"),
)
TICKETS = {
    "version": 1,
    "store": "github",
    "repo": "example/project",
    "label": "ticket",
    "human_label": "human-only",
    "request_label": "human-requested",
    "claims": ".outcomebound/ticket-claims.json",
}
TEST_LINE = "- when writing, changing or judging a test"
TICKETS_CONDITION = "or their declaration"
CWD_WARNINGS = frozenset({"tickets: the claim", "tickets: the claims plan"})

needs_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="mode 000 keeps a folder unreadable only for a POSIX user that is not root",
)


def git(cwd: Path, *argv: str, check: bool = True) -> str:
    done = subprocess.run(
        [GIT, *EXACT, "-C", str(cwd), *argv],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return done.stdout


def commit(project: Path, message: str) -> None:
    git(project, "add", "-A")
    git(project, *IDENTITY, "commit", "-q", "--allow-empty", "-m", message)


def engine(tree: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    """`outcomebound <argv>` run by the engine in `tree`."""

    return subprocess.run(
        [sys.executable, "-I", "-c", LAUNCH, str(tree), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.strip().lstrip("v").split("."))


def released_tags() -> list[str]:
    """This repository's release tags, oldest first; none where it is no Git checkout."""

    try:
        listed = git(ROOT, "tag", "--list", "v*")
    except (OSError, subprocess.CalledProcessError):
        return []
    tags = [tag for tag in listed.split() if re.fullmatch(r"v\d+\.\d+\.\d+", tag)]
    return sorted(tags, key=version)


def tag_tree(tag: str) -> str | None:
    """The tree that a tag of this repository names; None where Git cannot read it."""

    done = subprocess.run(
        [GIT, "-C", str(ROOT), "rev-parse", "--verify", "-q", f"{tag}^{{tree}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def candidate_tree() -> str | None:
    """The tree of the candidate: HEAD's tree where the candidate is this checkout, else None,
    since another engine tree (an archive) names no commit."""

    return tag_tree("HEAD") if ROOT.resolve() == CANDIDATE else None


def before_candidate(
    tags: list[str], ceiling: tuple[int, ...], own: str | None, tree_of: Callable[[str], str | None]
) -> list[str]:
    """The release tags the candidate can upgrade from, oldest first: at or below its `VERSION`,
    less a tag whose tree is the candidate's own, which is the release under test."""

    return [tag for tag in tags if version(tag) <= ceiling and (own is None or tree_of(tag) != own)]


def previous_tag(which: str) -> str:
    """The release that `which` names for the candidate, or a skip that says why none."""

    tags = released_tags()
    if which == "oldest":
        if OLDEST not in tags:
            pytest.skip(f"the tag {OLDEST} is not in this clone (a shallow clone or a fork)")
        return OLDEST
    ceiling = version((CANDIDATE / "VERSION").read_text(encoding="utf-8"))
    below = before_candidate(tags, ceiling, candidate_tree(), tag_tree)
    if not below:
        pytest.skip("no release tag before the candidate is in this clone")
    if below[-1] == OLDEST:
        pytest.skip(f"the release tag before the candidate is {OLDEST}, run as oldest")
    return below[-1]


TAGS = ["v1.0.0", "v1.1.0", "v1.1.1"]
TREES = {"v1.0.0": "tree-100", "v1.1.0": "tree-110", "v1.1.1": "tree-111", "v1.2.0": "tree-120"}


@pytest.mark.parametrize(
    ("tags", "candidate_version", "own", "expected"),
    [
        # Between releases: VERSION still names the previous release, whose tree is not HEAD's.
        pytest.param(TAGS, "1.1.1", "tree-dev", "v1.1.1", id="development"),
        # The release commit, before its tag exists.
        pytest.param(TAGS, "1.2.0", "tree-120", "v1.1.1", id="release-before-tag"),
        # The tag's pipeline: the tag exists and names the candidate's own tree.
        pytest.param([*TAGS, "v1.2.0"], "1.2.0", "tree-120", "v1.1.1", id="release-after-tag"),
        # After the release, VERSION names it and HEAD has moved on.
        pytest.param([*TAGS, "v1.2.0"], "1.2.0", "tree-dev", "v1.2.0", id="after-release"),
        # Another engine tree names no commit: the newest tag at or below its VERSION.
        pytest.param([*TAGS, "v1.2.0"], "1.2.0", None, "v1.2.0", id="archive-candidate"),
    ],
)
def test_the_release_before_the_candidate_is_the_one_it_upgrades_from(
    tags: list[str], candidate_version: str, own: str | None, expected: str
) -> None:
    below = before_candidate(tags, version(candidate_version), own, TREES.get)

    assert below[-1] == expected


@dataclass(frozen=True)
class Case:
    """One adopter shape: the previous install's options, what the project then holds, the
    warning kinds the upgrade prints, and, for the negative control, the refusal it gives. A
    `folder` puts the install in that subfolder of its Git work tree, as a component with its
    own install in a larger repository has it."""

    shape: Callable[[Path], None]
    expected: frozenset[str] = frozenset()
    install: tuple[str, ...] = INSTALL
    locks: tuple[str, ...] = ()
    unnamed: tuple[str, ...] = ()
    refusal: str = ""
    release: Callable[[Path], None] | None = None
    folder: str = ""


def plain(project: Path) -> None:
    """The install as the previous release left it, committed."""


def claims(cwd: str | None, planned: bool = False) -> Callable[[Path], None]:
    """A tickets claims plan in `.outcomebound/`, written for the checkout root, with the given
    `cwd`: its claim declares `app.py`, which the root holds, and where `planned`,
    `tests/test_new.py`, which an open ticket will add and no folder holds yet."""

    def shape(project: Path) -> None:
        claim: dict[str, object] = {
            "name": "unit",
            "command": ["true"],
            "required_paths": ["app.py", *(["tests/test_new.py"] if planned else [])],
        }
        plan: dict[str, object] = {"version": 1, "claims": [claim]}
        if cwd is not None:
            plan["cwd"] = cwd
        write(project / ".outcomebound/ticket-claims.json", json.dumps(plan) + "\n")
        write(project / ".outcomebound/tickets.json", json.dumps(TICKETS) + "\n")
        commit(project, "plan")

    return shape


def edit_alike(text: str) -> str:
    assert text.count("does not tell you") == 1
    return text.replace("does not tell you", "does not show here")


def local_edited_alike(project: Path) -> None:
    """The project's local fragment and the pointers block that inlines it, edited the same way
    and committed: the block is what the candidate writes from the fragment, not its record."""

    for name in (".outcomebound/fragments/local.md", "AGENTS.md"):
        path = project / name
        write(path, edit_alike(path.read_text(encoding="utf-8")))
    commit(project, "local fragment")


def local_edited_in_block_only(project: Path) -> None:
    """The negative control: the same edit in the block alone, so the block is neither its
    record nor what the candidate writes."""

    path = project / "AGENTS.md"
    write(path, edit_alike(path.read_text(encoding="utf-8")))
    commit(project, "block edit")


def local_and_pointer_line_edited(project: Path) -> None:
    """The negative control for a block rendered anew: the local fragment and the block edited
    the same way, and a pointer line in the block edited too, so the block is not the previous
    render of the fragment as it is now."""

    local_edited_alike(project)
    path = project / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    assert text.count(TEST_LINE) == 1
    write(path, text.replace(TEST_LINE, "- when writing or judging a test"))
    commit(project, "pointer line")


def tickets_condition_reworded(tree: Path) -> None:
    """A release that renders the pointers block anew: the tickets fragment's condition, which
    its pointer line carries, says it in other words."""

    path = tree / "fragments/setup/tickets.md"
    text = path.read_text(encoding="utf-8")
    assert text.count(TICKETS_CONDITION) == 1
    write(path, text.replace(TICKETS_CONDITION, f"{TICKETS_CONDITION} file"))


def unreadable_folder(project: Path) -> None:
    """A folder that holds a `.git`, as a nested repository does; the test makes it mode 000."""

    (project / "locked/.git").mkdir(parents=True)


def ignored_copies(project: Path) -> None:
    """Two scratch copies of the project under the ignored `.agents/work/`, each with an
    AGENTS.md that alone is past codex's cap; another clone does not get them."""

    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    for name in ("copy-a", "copy-b"):
        copy = project / ".agents/work" / name
        copy.mkdir(parents=True)
        write(copy / "AGENTS.md", text + "x" * CAP)
        write(copy / "app.py", "")
    assert git(project, "check-ignore", ".agents/work/copy-a/AGENTS.md").strip()


def nested_repository(project: Path) -> None:
    """A nested Git repository with its own AGENTS.md past codex's cap: it is its own project."""

    nested = project / "vendor/lib"
    nested.mkdir(parents=True)
    git(nested, "init", "-q")
    write(nested / "AGENTS.md", "n" * CAP)
    commit(nested, "nested")


def staged_change(project: Path) -> None:
    """A change and a new file staged, and a change not staged, all to the project's files."""

    write(project / "app.py", "print('staged')\n")
    (project / "src").mkdir()
    write(project / "src/new.py", "NEW = 1\n")
    git(project, "add", "app.py", "src/new.py")
    write(project / "README.md", "# Project\n\nNot staged.\n")


def crlf_checkout(project: Path) -> None:
    """The project as a Windows checkout with `core.autocrlf=true` holds it: every file the
    install wrote, and the project's own local fragment, with CRLF line endings, committed.
    The previous release recorded the digests of the LF text it wrote."""

    own, _ = own_paths(project)
    for relative in sorted({*own, ".outcomebound/fragments/local.md"}):
        path = project / relative
        data = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(data.replace(b"\n", b"\r\n"))
    commit(project, "crlf checkout")


CASES = {
    "plain": Case(plain),
    "crlf-checkout": Case(crlf_checkout),
    "plan-no-cwd": Case(claims(None), CWD_WARNINGS),
    "plan-dot": Case(claims("."), CWD_WARNINGS),
    "plan-dotdot": Case(claims("..")),
    "plan-dot-planned": Case(claims(".", planned=True), CWD_WARNINGS, unnamed=("test_new.py",)),
    "plan-dotdot-planned": Case(claims("..", planned=True)),
    "local-edited-alike": Case(local_edited_alike, install=LOCAL_ONLY),
    "local-edited-in-block-only": Case(
        local_edited_in_block_only,
        install=LOCAL_ONLY,
        refusal="AGENTS.md (guidance-pointers) differs from what adopt wrote",
    ),
    "local-edited-alike-rendered-anew": Case(
        local_edited_alike, release=tickets_condition_reworded
    ),
    "subfolder-local-edited-alike-rendered-anew": Case(
        local_edited_alike, release=tickets_condition_reworded, folder="component"
    ),
    "local-and-pointer-line-edited-rendered-anew": Case(
        local_and_pointer_line_edited,
        refusal="AGENTS.md (guidance-pointers) differs from what adopt wrote",
        release=tickets_condition_reworded,
    ),
    "unreadable-folder": Case(unreadable_folder, locks=("locked",)),
    "ignored-copies": Case(ignored_copies),
    "nested-repository": Case(nested_repository),
    "staged-change": Case(staged_change),
    "finish-check": Case(plain, install=FINISH),
}
MARKS = {"unreadable-folder": needs_permissions}


@pytest.fixture(scope="session")
def tag_engine(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    """The engine of a release tag, from `git archive` with LF line endings (`EXACT`), built once
    per test process."""

    engines: dict[str, Path] = {}

    def engine_of(tag: str) -> Path:
        if tag not in engines:
            tree = tmp_path_factory.mktemp(f"engine-{tag}")
            archive = subprocess.run(
                [GIT, *EXACT, "-C", str(ROOT), "archive", "--format=zip", tag],
                check=True,
                capture_output=True,
            ).stdout
            with zipfile.ZipFile(io.BytesIO(archive)) as files:
                files.extractall(tree)
            engines[tag] = tree
        return engines[tag]

    return engine_of


@pytest.fixture(scope="session")
def installed(
    tmp_path_factory: pytest.TempPathFactory, tag_engine: Callable[[str], Path]
) -> Callable[[str, tuple[str, ...], str], Path]:
    """The Git work tree whose `folder` holds the project as the engine of a release tag
    installed it with given options, committed; each install is built once per test process."""

    installs: dict[tuple[str, tuple[str, ...], str], Path] = {}

    def install(tag: str, options: tuple[str, ...], folder: str = "") -> Path:
        key = (tag, options, folder)
        if key not in installs:
            tree = tag_engine(tag)
            work_tree = tmp_path_factory.mktemp("installed") / "project"
            work_tree.mkdir()
            git(work_tree, "init", "-q")
            project = work_tree / folder
            project.mkdir(exist_ok=True)
            write(project / "AGENTS.md", "# Project\n\nThe project's own words.\n")
            write(project / "README.md", "# Project\n")
            write(project / "app.py", "print('app')\n")
            local = project / ".outcomebound/fragments/local.md"
            local.parent.mkdir(parents=True)
            shutil.copyfile(tree / "templates/fragment-local.md", local)
            commit(project, "project")
            done = engine(tree, "adopt", str(project), *options)
            assert done.returncode == 0, f"{tag} install: {done.stdout}{done.stderr}"
            commit(project, f"OutcomeBound {tag}")
            installs[key] = work_tree
        return installs[key]

    return install


@pytest.fixture(scope="session")
def released(tmp_path_factory: pytest.TempPathFactory) -> Callable[[Callable[[Path], None]], Path]:
    """The candidate engine as a release changed by `release`, copied once per test process."""

    trees: dict[Callable[[Path], None], Path] = {}

    def build(release: Callable[[Path], None]) -> Path:
        if release not in trees:
            tree = tmp_path_factory.mktemp("candidate") / "engine"
            ignored = shutil.ignore_patterns(".git", ".agents", "__pycache__", "dist")
            shutil.copytree(CANDIDATE, tree, ignore=ignored)
            release(tree)
            trees[release] = tree
        return trees[release]

    return build


@pytest.fixture
def unlock() -> Iterator[list[Path]]:
    """Folders a case made mode 000, given their mode back at teardown so pytest removes them."""

    locked: list[Path] = []
    yield locked
    for folder in reversed(locked):
        folder.chmod(0o755)


def warnings(out: str) -> list[str]:
    return [line.split(None, 1)[1] for line in out.splitlines() if line.startswith("warning ")]


def edited(out: str) -> list[str]:
    """The records `adopt --check` reads `edited`: bytes the project changed, which an upgrade
    refuses to replace without --force."""

    return [line for line in out.splitlines() if line.startswith("edited ")]


def kind(text: str) -> str:
    for pattern, label in KINDS:
        found = pattern.match(text)
        if found:
            return label.format(*found.groups())
    return text


def own_paths(project: Path) -> tuple[set[str], set[str]]:
    """The paths the install records, and of them those that hold blocks in a project's file."""

    manifest = project / ".outcomebound/manifest.json"
    if not manifest.is_file():
        return set(), set()
    records = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
    paths = {record["path"] for record in records} | {".outcomebound/manifest.json"}
    return paths, {record["path"] for record in records if record["kind"] == "block"}


def state(project: Path, skip: set[str], blocks: set[str]) -> dict[str, object]:
    """What the project holds outside `skip`: each file's bytes, a block file with its blocks
    taken out, `git status` and the index. os.walk passes over a folder it cannot list."""

    files: dict[str, bytes] = {}
    for here, folders, names in os.walk(project):
        folders[:] = [name for name in folders if name != ".git"]
        for name in names:
            path = Path(here, name)
            relative = path.relative_to(project).as_posix()
            if relative in blocks:
                files[relative] = BLOCK.sub(
                    r"<block \1>", path.read_text(encoding="utf-8")
                ).encode()
            elif relative not in skip:
                files[relative] = path.read_bytes()
    status = git(project, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored")
    # Porcelain status names paths from the work tree's root; `skip` names them from `project`.
    prefix = git(project, "rev-parse", "--show-prefix").strip()
    return {
        "files": files,
        "status": sorted(
            entry for entry in status.split("\0") if entry[3:].removeprefix(prefix) not in skip
        ),
        "index": git(project, "ls-files", "--stage"),
    }


@pytest.mark.parametrize("previous", ["oldest", "latest"])
@pytest.mark.parametrize("name", [pytest.param(name, marks=MARKS.get(name, ())) for name in CASES])
def test_an_install_of_a_previous_release_upgrades_with_the_candidate(
    tmp_path: Path,
    installed: Callable[[str, tuple[str, ...], str], Path],
    released: Callable[[Callable[[Path], None]], Path],
    unlock: list[Path],
    name: str,
    previous: str,
) -> None:
    """The candidate reads no project edit where there is none, upgrades each shape without
    stopping, refuses only the block that differs from both its record and its render, reads
    every record current after, warns of exactly the kinds the case expects, and leaves every
    file, status and index entry it does not record as it found them. A case with a `release`
    upgrades with the candidate changed as that release would change it."""

    case = CASES[name]
    work_tree = tmp_path / "project"
    installs = installed(previous_tag(previous), case.install, case.folder)
    shutil.copytree(installs, work_tree, symlinks=True)
    project = work_tree / case.folder
    case.shape(project)
    for folder in case.locks:
        (project / folder).chmod(0)
        unlock.append(project / folder)
    own_before, blocks = own_paths(project)
    before = state(project, own_before, blocks)
    whole = state(project, set(), set()) if case.refusal else {}

    candidate = released(case.release) if case.release else CANDIDATE
    first = engine(candidate, "adopt", str(project), "--check")
    upgrade = engine(candidate, "adopt", str(project))
    check = engine(candidate, "adopt", str(project), "--check")

    assert bool(edited(first.stdout)) == bool(case.refusal), first.stdout
    report = f"{upgrade.stdout}{upgrade.stderr}"
    assert "Traceback" not in upgrade.stderr, report
    if case.refusal:
        assert upgrade.returncode == 1, report
        assert case.refusal in upgrade.stderr, report
        assert state(project, set(), set()) == whole, "a refusal writes nothing"
        assert check.returncode != 0, check.stdout
        return
    assert upgrade.returncode == 0, report
    lines = warnings(upgrade.stdout)
    assert {kind(line) for line in lines} == case.expected, lines
    assert not [line for line in lines for word in case.unnamed if word in line], lines
    assert check.returncode == 0, check.stdout
    own_after, blocks_after = own_paths(project)
    assert blocks_after == blocks
    assert state(project, own_before | own_after, blocks) == before


def pointers_record(project: Path) -> dict[str, object]:
    artifacts = json.loads((project / ".outcomebound/manifest.json").read_text(encoding="utf-8"))
    (record,) = [r for r in artifacts["artifacts"] if r["id"] == "guidance-pointers"]
    return dict(record)


@pytest.mark.parametrize("previous", ["oldest", "latest"])
def test_a_previous_release_reads_the_candidates_manifest_and_the_candidate_reads_its_rewrite(
    tmp_path: Path,
    installed: Callable[[str, tuple[str, ...], str], Path],
    tag_engine: Callable[[str], Path],
    released: Callable[[Callable[[Path], None]], Path],
    previous: str,
) -> None:
    """The `frame` field needs no new manifest format: the candidate's upgrade adds it, the
    previous release's engine reads that manifest and, when it writes the manifest again, keeps
    the field if it writes `frame` itself and drops it if it predates the field, and the candidate
    then decides an edit of the local fragment alone, from the fragment's history in Git where the
    field was dropped. Breaks if the candidate writes no frame, if the previous release refuses the
    candidate's manifest, or if the candidate refuses the block after the rewrite."""

    tag = previous_tag(previous)
    project = tmp_path / "project"
    shutil.copytree(installed(tag, INSTALL, ""), project, symlinks=True)
    # A release from 1.2.0 on writes `frame` itself; an earlier one predates it.
    older_writes_frame = "frame" in pointers_record(project)

    upgrade = engine(CANDIDATE, "adopt", str(project))
    assert upgrade.returncode == 0, f"{upgrade.stdout}{upgrade.stderr}"
    assert "frame" in pointers_record(project)
    commit(project, "candidate")

    older = tag_engine(tag)
    # The candidate renders some blocks and files anew, so the previous release reads them stale;
    # what matters is that it reads the manifest, and reads no record edited.
    check = engine(older, "adopt", str(project), "--check")
    assert "Traceback" not in check.stderr and "manifest" not in check.stderr, check.stderr
    assert check.stdout.startswith(("current ", "stale ")), check.stdout
    assert not edited(check.stdout), check.stdout
    rewrite = engine(older, "adopt", str(project))
    assert rewrite.returncode == 0, f"{rewrite.stdout}{rewrite.stderr}"
    assert ("frame" in pointers_record(project)) == older_writes_frame
    commit(project, f"OutcomeBound {tag} again")

    local_edited_alike(project)
    candidate = released(tickets_condition_reworded)
    first = engine(candidate, "adopt", str(project), "--check")
    assert not edited(first.stdout), first.stdout
    upgrade = engine(candidate, "adopt", str(project))
    assert upgrade.returncode == 0, f"{upgrade.stdout}{upgrade.stderr}"
    assert any(line.startswith("render ") for line in upgrade.stdout.splitlines()), upgrade.stdout
    assert "frame" in pointers_record(project)
    assert engine(candidate, "adopt", str(project), "--check").returncode == 0
