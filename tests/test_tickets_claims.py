"""The claims plan: lookup and containment.

Every test builds its own scratch repository under `tmp_path` and writes the
identity into that repository's own config, so a runner with no global git
identity reads the same as any other. Claims are commands built from this
interpreter, so no test depends on a tool being installed.
"""

from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path

import pytest

from outcomebound_tools import validation
from outcomebound_tools.tickets_claims import ClaimDefinition, load_claims
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_git import git
from outcomebound_tools.tickets_report import Refusal

PLAN = ".outcomebound/ticket-claims.json"


# --- scratch repositories and plans ----------------------------------------------


def _git(root: Path, *arguments: str) -> None:
    """A setup command that must have worked, with git's own message on failure."""

    outcome = git(root, *arguments)
    assert outcome.status == 0, outcome.stderr.decode("utf-8", "replace")


def _repository(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "tickets@example.invalid")
    _git(root, "config", "user.name", "Ticket Tests")
    _git(root, "config", "commit.gpgsign", "false")
    return root


def _declaration(claims: str = PLAN) -> Declaration:
    return Declaration(
        store="github",
        repo="owner/project",
        label="ob-ticket",
        human_label="human-only",
        request_label="human-requested",
        claims=claims,
    )


def _claim(name: str, command: list[str], **extra: object) -> dict[str, object]:
    return {
        "name": name,
        "risk": f"{name} is not checked",
        "kind": "static",
        "command": command,
        **extra,
    }


def _plan_document(claims: list[dict[str, object]], **top: object) -> dict[str, object]:
    return {"version": 1, "claims": claims, **top}


def _write_plan(root: Path, document: object, relative: str = PLAN) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1), encoding="utf-8")


def _write_text(root: Path, text: str, relative: str = PLAN) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# Commands that need no installed tool: this interpreter, asked for one exit status.
def _exit(code: int) -> list[str]:
    return [sys.executable, "-c", f"raise SystemExit({code})"]


# --- where a relative `cwd` starts ------------------------------------------------


def test_cwd_resolves_against_the_plan_folder_as_validation_does(tmp_path: Path) -> None:
    """A relative `cwd` starts at the plan file's folder, where `validation` starts it.

    `"cwd": ".."` from `.outcomebound/` is the checkout root, and both readers
    name that same directory, so one plan runs in one place under both verbs.
    """

    root = _repository(tmp_path)
    (root / "work").mkdir()
    document = _plan_document([_claim("here", _exit(0))], cwd="../work")
    _write_plan(root, document)

    plan = load_claims(root, _declaration())

    assert plan.cwd_inside is True
    assert plan.cwd_resolved == (root / "work").resolve()
    ran = validation.load_plan(root / PLAN)
    assert ran.cwd == plan.cwd_resolved, "both verbs resolve the one plan to one directory"


def test_cwd_outside_the_checkout_is_reported(tmp_path: Path) -> None:
    """The resolved directory is still named, and read as outside."""

    root = _repository(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _write_plan(root, _plan_document([_claim("out", _exit(0))], cwd="../../elsewhere"))

    plan = load_claims(root, _declaration())

    assert plan.cwd_inside is False
    assert plan.cwd_resolved == elsewhere.resolve()


def test_an_empty_readable_plan_still_answers_containment(tmp_path: Path) -> None:
    """A plan of no claims is readable, and still names a directory to report.

    This is why the containment answer is a field on the plan: there is no
    `ClaimDefinition` here to carry it, and `check` must still report
    `CLAIM_CWD_OUTSIDE`.
    """

    root = _repository(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _write_plan(root, {"version": 1, "claims": [], "cwd": "../../elsewhere"})

    plan = load_claims(root, _declaration())

    assert dict(plan.claims) == {}
    assert plan.cwd_inside is False
    assert plan.cwd_resolved == elsewhere.resolve()


def test_a_symlinked_checkout_is_inside_itself(tmp_path: Path) -> None:
    """Both sides resolved: a checkout reached through a link is not outside itself."""

    real = _repository(tmp_path, "real")
    (real / "work").mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    _write_plan(real, _plan_document([_claim("here", _exit(0))], cwd=".."))

    through_link = load_claims(link, _declaration())
    assert through_link.cwd_inside is True
    assert through_link.cwd_resolved == real.resolve()

    # A link *inside* the checkout, pointing inside it, is inside it too.
    (real / "linked-work").symlink_to(real / "work", target_is_directory=True)
    _write_plan(real, _plan_document([_claim("here", _exit(0))], cwd="../linked-work"))
    followed = load_claims(real, _declaration())
    assert followed.cwd_inside is True
    assert followed.cwd_resolved == (real / "work").resolve()


def test_cwd_absent_is_the_plan_folder(tmp_path: Path) -> None:
    """The key omitted is the plan file's folder, as `validation` reads it."""

    root = _repository(tmp_path)
    _write_plan(root, _plan_document([_claim("here", _exit(0))]))

    plan = load_claims(root, _declaration())

    assert plan.cwd_inside is True
    assert plan.cwd_resolved == (root / ".outcomebound").resolve()
    assert validation.load_plan(root / PLAN).cwd == plan.cwd_resolved


def test_required_paths_are_named_relative_to_the_checkout(tmp_path: Path) -> None:
    """A claim's required paths resolve against the plan's directory, and one
    outside the checkout reads as None, which no `bounds` entry can cover."""

    root = _repository(tmp_path)
    claim = _claim("reads", _exit(0), required_paths=["src/feature", ".", "../../outside"])
    _write_plan(root, _plan_document([claim], cwd=".."))

    plan = load_claims(root, _declaration())

    assert plan.claims["reads"].required_paths == ("src/feature", ".", None)


def test_a_claim_name_the_ticket_grammar_forbids_is_still_readable(tmp_path: Path) -> None:
    """The plan is one namespace; which names a ticket may cite is the block's rule."""

    root = _repository(tmp_path)
    _write_plan(root, _plan_document([_claim("has.a.dot", _exit(0))]))

    plan = load_claims(root, _declaration())

    assert "has.a.dot" in plan.claims


# --- reading the working tree -----------------------------------------------------


def test_working_tree_read_refuses_by_name(tmp_path: Path) -> None:
    """A verb that cannot read the plan reports nothing about claims."""

    root = _repository(tmp_path)

    def _refusal() -> Refusal:
        with pytest.raises(Refusal) as raised:
            load_claims(root, _declaration())
        assert raised.value.code == "CLAIMS_UNREADABLE"
        assert PLAN in raised.value.text
        return raised.value

    _refusal()  # absent in the working tree

    _write_text(root, "{ truncated")
    _refusal()  # not JSON

    _write_plan(root, {"version": 1})
    _refusal()  # `claims` absent

    _write_plan(root, {"version": 1, "claims": {"here": {}}})
    _refusal()  # `claims` is not a list

    _write_plan(root, _plan_document([{"risk": "r", "kind": "static", "command": _exit(0)}]))
    _refusal()  # an item with no name

    _write_plan(root, _plan_document([_claim("twice", _exit(0)), _claim("twice", _exit(1))]))
    assert "twice" in _refusal().text  # one name, twice: the plan is one namespace

    _write_plan(root, _plan_document([_claim("here", _exit(0))], cwd=7))
    _refusal()  # a top-level `cwd` that is not a string

    _write_plan(root, _plan_document([_claim("here", _exit(0))], timeout_seconds="soon"))
    _refusal()  # a top-level `timeout_seconds` that is not a number


def test_a_cwd_holding_a_nul_is_unreadable_by_name(tmp_path: Path) -> None:
    """A top-level `cwd` holding a NUL byte is a plan no verb can read, named as such."""

    root = _repository(tmp_path)
    _write_plan(root, _plan_document([_claim("here", _exit(0))], cwd="a\0b"))

    with pytest.raises(Refusal) as tree:
        load_claims(root, _declaration())
    assert tree.value.code == "CLAIMS_UNREADABLE"
    assert "the top-level cwd contains a NUL byte" in tree.value.text


def test_a_symlinked_plan_path_is_refused(tmp_path: Path) -> None:
    """The bounded read refuses a symlinked component rather than following it."""

    root = _repository(tmp_path)
    (root / "elsewhere.json").write_text(
        json.dumps(_plan_document([_claim("here", _exit(0))])), encoding="utf-8"
    )
    (root / ".outcomebound").mkdir()
    (root / PLAN).symlink_to(root / "elsewhere.json")

    with pytest.raises(Refusal) as raised:
        load_claims(root, _declaration())
    assert raised.value.code == "CLAIMS_UNREADABLE"


# --- what a definition carries ----------------------------------------------------


def test_definitions_carry_command_and_timeout(tmp_path: Path) -> None:
    """The timeout in effect: the claim's own, else the plan's, else none at all."""

    root = _repository(tmp_path)
    _write_plan(
        root,
        _plan_document(
            [_claim("own", _exit(0), timeout_seconds=7), _claim("plans", _exit(1))],
            timeout_seconds=19,
        ),
    )
    plan = load_claims(root, _declaration())

    assert plan.claims["own"].timeout_seconds == 7.0
    assert plan.claims["plans"].timeout_seconds == 19.0
    assert plan.claims["plans"].command == tuple(_exit(1))
    assert isinstance(plan.claims["own"], ClaimDefinition)

    _write_plan(root, _plan_document([_claim("neither", _exit(0))]))
    bare = load_claims(root, _declaration())
    assert bare.claims["neither"].timeout_seconds is None

    # Written order, which is the order `brief` renders.
    _write_plan(root, _plan_document([_claim("b", _exit(0)), _claim("a", _exit(0))]))
    assert list(load_claims(root, _declaration()).claims) == ["b", "a"]


def test_the_timeout_rendered_is_the_timeout_the_runner_gives_the_claim(tmp_path: Path) -> None:
    """Compared against the runner's own parsed value, never a hand-written number.

    `ClaimDefinition.timeout_seconds` is what `brief` renders, so where the
    claim or the plan sets a timeout it has to be the one that would apply,
    including where the claim declares none and inherits the plan's. Where
    neither sets one the claim has no timeout, which `brief` says as such.
    """

    root = _repository(tmp_path)
    document = _plan_document(
        [_claim("own", _exit(0), timeout_seconds=7), _claim("inherits", _exit(0))],
        timeout_seconds=19,
    )
    _write_plan(root, document)
    rendered = load_claims(root, _declaration()).claims
    runner = {
        claim.name: claim.timeout_seconds
        for claim in validation.parse_plan(document, invocation_cwd=root).claims
    }
    assert {name: item.timeout_seconds for name, item in rendered.items()} == runner

    _write_plan(root, _plan_document([_claim("inherits", _exit(0))]))
    assert load_claims(root, _declaration()).claims["inherits"].timeout_seconds is None


# --- the seam ---------------------------------------------------------------------


def test_tests_import_only_public_names() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
    reached = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if not node.module.startswith("outcomebound_tools.tickets"):
            continue
        public = set(importlib.import_module(node.module).__all__)
        for alias in node.names:
            reached += 1
            assert alias.name in public, f"{node.module}.{alias.name} is not in __all__"
    assert reached == 5, "this file imports exactly the seam it tests"
