"""`tickets publish`: the script that publishes drafts, run against a stand-in `gh`.

The script is run with `sh`, with a `gh` on PATH that records each call and the
body it was given and answers as `gh issue create` does, with an issue URL. So
each test reads what the tracker would have been asked, and no network is used.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from outcomebound_tools.tickets import main
from outcomebound_tools.tickets_declaration import DECLARATION_PATH
from outcomebound_tools.tickets_model import parse_block

CLAIMS_PATH = ".outcomebound/ticket-claims.json"
CLAIM = "example-claim"
REPO = "owner/project"

# Answers each `gh issue create` with the next issue URL, and records the
# arguments and the body read from standard input, one JSON line per call.
_FAKE_GH = f"""#!{sys.executable}
import json, os, sys
log = os.environ["FAKE_GH_LOG"]
if sys.argv[1:3] == ["issue", "create"] and "--help" in sys.argv:
    print("--blocked-by numbers  --parent number")
    raise SystemExit(0)
calls = sum(1 for _ in open(log)) if os.path.exists(log) else 0
body = sys.stdin.read() if "--body-file" in sys.argv else ""
with open(log, "a") as out:
    out.write(json.dumps({{"argv": sys.argv[1:], "body": body}}) + "\\n")
print(f"https://github.com/{REPO}/issues/{{100 + calls}}")
"""


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def checkout(tmp_path: Path, **declared: object) -> Path:
    root = tmp_path / "repo"
    document = {
        "version": 1,
        "store": "github",
        "repo": REPO,
        "label": "ob-ticket",
        "human_label": "human-only",
        "request_label": "human-requested",
        "claims": CLAIMS_PATH,
        **declared,
    }
    write(root, DECLARATION_PATH, json.dumps(document))
    plan = {"version": 1, "cwd": "..", "claims": [{"name": CLAIM, "command": ["true"]}]}
    write(root, CLAIMS_PATH, json.dumps(plan))
    return root


def draft(title: str, *keys: str, hold: str = "no", prose: str = "") -> str:
    lines = [
        f"# {title}",
        "",
        "## Outcome",
        prose or f"{title} becomes observably true; it costs $HOME and `$(date)` nothing.",
        "",
        "<!-- outcomebound:begin id=ticket v=1 -->",
        "bounds: src",
        f"human-only: {hold}",
        "done-when:",
        f"- {CLAIM}",
        *keys,
        "<!-- outcomebound:end id=ticket -->",
    ]
    return "\n".join(lines) + "\n"


def script(root: Path, *paths: Path, capsys: pytest.CaptureFixture[str]) -> str:
    code = main(["publish", str(root), "--draft", *map(str, paths)])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert captured.err == ""
    return captured.out


def run(tmp_path: Path, text: str) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
    """Run the printed script with the stand-in `gh` first on PATH."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "gh.log"
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_LOG": str(log),
    }
    shell = shutil.which("sh")
    assert shell is not None
    ran = subprocess.run(
        [shell, "-c", text], env=environment, capture_output=True, text=True, check=False
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return ran, calls


def flag(argv: list[str], name: str) -> list[str]:
    return [argv[index + 1] for index, word in enumerate(argv) if word == name]


@pytest.mark.skipif(os.name != "posix", reason="the script is POSIX shell")
def test_drafts_are_published_in_relation_order_with_their_relations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A draft is created after each sibling it names, its relations are `gh` flags
    naming the siblings' new numbers, and its body drops the keys the tracker holds
    and names a sibling `discovered-from` by its number. The prose reaches the
    tracker byte for byte, shell characters included, and so do the file names."""

    root = checkout(tmp_path)
    folder = 'drafts "$HOME"'
    child = write(
        tmp_path,
        f"{folder}/child.md",
        draft("Child", "blocked-by: blocker, #7", "parent: epic", "discovered-from: blocker"),
    )
    blocker = write(tmp_path, f"{folder}/blocker.md", draft("Blocker", hold="yes"))
    epic = write(tmp_path, f"{folder}/epic.md", draft("Epic", "blocked-by: owner/other#3"))

    text = script(root, child, blocker, epic, capsys=capsys)
    ran, calls = run(tmp_path, text)

    assert ran.returncode == 0, ran.stderr
    creates = [call for call in calls if "--help" not in call["argv"]]
    titles = [flag(call["argv"], "--title")[0] for call in creates]
    assert titles == ["Blocker", "Epic", "Child"], "each sibling a draft names comes first"
    blocker_call, epic_call, child_call = creates
    assert flag(blocker_call["argv"], "--label") == ["ob-ticket", "human-only"]
    assert flag(epic_call["argv"], "--blocked-by") == ["https://github.com/owner/other/issues/3"]
    assert flag(child_call["argv"], "--parent") == ["101"]
    assert flag(child_call["argv"], "--blocked-by") == ["100,7"]
    assert flag(child_call["argv"], "--repo") == [REPO]

    body = child_call["body"]
    assert not body.startswith("# Child") and body.startswith("## Outcome")
    assert "$HOME and `$(date)`" in body, "the shell read no byte of the body"
    fields, messages = parse_block(body)
    assert messages == ()
    assert fields.blocked_by == () and fields.parent == "", "the tracker holds these"
    assert fields.discovered_from == "#100"
    assert f"{folder}/child.md -> #102" in ran.stdout


def test_a_draft_check_refuses_is_not_published(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Any ERROR `check --draft` reports stops the publish: no script, exit 1."""

    root = checkout(tmp_path)
    broken = write(tmp_path, "drafts/broken.md", draft("Broken", "blocked-by: nowhere"))

    code = main(["publish", str(root), "--draft", str(broken)])
    captured = capsys.readouterr()

    assert (code, captured.out) == (1, "")
    assert captured.err.startswith("PUBLISH_REFUSED: ") and "nowhere" in captured.err


def test_a_ring_through_discovered_from_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No order creates the first of two drafts that each were found from the other."""

    root = checkout(tmp_path)
    one = write(tmp_path, "drafts/one.md", draft("One", "discovered-from: two"))
    two = write(tmp_path, "drafts/two.md", draft("Two", "discovered-from: one"))

    code = main(["publish", str(root), "--draft", str(one), str(two)])
    captured = capsys.readouterr()

    assert (code, captured.out) == (1, "")
    assert captured.err.startswith("PUBLISH_REFUSED: ") and "ring" in captured.err


def test_the_header_names_the_writes_grant_or_its_absence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The engine runs nothing; the script says who may run it."""

    path = write(tmp_path, "drafts/one.md", draft("One"))

    ungranted = script(checkout(tmp_path), path, capsys=capsys)
    assert "records no `writes` grant: a person reviews this script" in ungranted

    shutil.rmtree(tmp_path / "repo")
    granted_root = checkout(tmp_path, writes={"granted_by": "a-maintainer", "on": "2026-10-04"})
    granted = script(granted_root, path, capsys=capsys)
    assert "Tracker writes granted by a-maintainer on 2026-10-04" in granted


def test_publish_needs_drafts_and_reads_no_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = checkout(tmp_path)
    path = write(tmp_path, "drafts/one.md", draft("One"))
    for argv in (
        ["publish", str(root)],
        ["publish", str(root), "--draft", str(path), "--input", "x"],
    ):
        with pytest.raises(SystemExit) as raised:
            main(argv)
        assert raised.value.code == 2
        assert "usage:" in capsys.readouterr().err


def test_a_draft_holding_a_nul_byte_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No shell argument carries a NUL byte, so the tracker would get other text."""

    root = checkout(tmp_path)
    path = write(tmp_path, "drafts/nul.md", draft("Nul", prose="a\0b"))

    code = main(["publish", str(root), "--draft", str(path)])
    captured = capsys.readouterr()

    assert (code, captured.out) == (1, "")
    assert captured.err.startswith("PUBLISH_REFUSED: ") and "NUL" in captured.err


@pytest.mark.skipif(os.name != "posix", reason="the script is POSIX shell")
def test_a_body_that_cannot_be_built_stops_the_script_before_gh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The body is built in an assignment, so a part that fails under `set -u` stops
    the run before `gh issue create` is asked; it is never on the left of a pipe."""

    root = checkout(tmp_path)
    found = write(tmp_path, "drafts/found.md", draft("Found"))
    later = write(tmp_path, "drafts/later.md", draft("Later", "discovered-from: found"))
    text = script(root, later, found, capsys=capsys)
    broken = "\n".join(line for line in text.splitlines() if not line.startswith("ob_1="))

    ran, calls = run(tmp_path, broken)

    assert ran.returncode != 0
    titles = [flag(call["argv"], "--title") for call in calls if "--help" not in call["argv"]]
    assert titles == [["Found"]], "the issue whose body failed was never created"
