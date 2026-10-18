"""The `verify` verb: it runs the claims one ticket's `done-when` names and no others, through
the runner of `outcomebound validation`, and reads them as one verdict.

Every fixture is the `brief` tests' checkout (a scratch Git repository, an export beside it and
a claims plan in `.outcomebound/`), with a plan whose commands each write a marker file at a path
the test names, so what ran is read from the disk and not from the verb's own report. The verb is
driven through `tickets.main(argv)` with the streams captured, since its result is a printed
verdict and an exit code.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools.tickets import main
from tests.test_tickets_brief import (
    CLAIMS_PATH,
    block,
    checkout,
    draft_document,
    exported,
    plan_document,
    ticket_document,
    write,
)

CHECKS = ".outcomebound/.outcomebound-checks"


def command(marker: Path, exit_code: int = 0) -> list[str]:
    """A claim's argv: write `marker`, then exit with `exit_code`."""

    code = (
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran'); "
        f"raise SystemExit({exit_code})"
    )
    return [sys.executable, "-c", code]


def claim(markers: Path, name: str, exit_code: int = 0, **fields: object) -> dict[str, object]:
    return {
        "name": name,
        "risk": f"{name} is wrong",
        "kind": "test",
        "command": command(markers / name, exit_code),
        **fields,
    }


def ran(markers: Path) -> set[str]:
    return {path.name for path in markers.iterdir()}


def project(
    tmp_path: Path,
    claims: Sequence[Mapping[str, object]],
    done_when: Sequence[str],
    **keys: Any,
) -> tuple[Path, Path]:
    """A checkout whose ticket `#1` names `done_when`, and the folder the markers go in."""

    markers = tmp_path / "markers"
    markers.mkdir()
    root = checkout(
        tmp_path,
        ticket_document(done_when=done_when, **keys),
        plan=plan_document(claims),
    )
    return root, markers


def verify(root: Path, *arguments: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    source = exported(root)
    given = () if "--draft" in arguments or "--input" in arguments else ("--input", str(source))
    capsys.readouterr()
    code = main(["verify", str(root), *arguments, *given])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def lines(out: str) -> list[str]:
    return out.splitlines()


def records(root: Path) -> list[dict[str, Any]]:
    found = sorted((root / CHECKS).glob("*.result.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in found]


def test_only_the_claims_the_ticket_names_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plan claim the ticket does not name is not run; the ones it names are, in plan order."""

    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path,
        [claim(markers, "alpha"), claim(markers, "beta"), claim(markers, "gamma")],
        ["gamma", "alpha: red-first"],
    )

    code, out, err = verify(root, "1", capsys=capsys)

    assert (code, err) == (0, "")
    assert ran(markers) == {"alpha", "gamma"}
    rows = lines(out)
    assert [row.split()[:2] for row in rows[:-1]] == [["PASS", "alpha"], ["PASS", "gamma"]]
    assert rows[-1] == "VERDICT: PASS (done-when of #1: 2 PASS)"
    assert sorted(record["claim"] for record in records(root)) == ["alpha", "gamma"]


def test_each_attempt_is_kept_as_the_runner_keeps_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A verified run leaves the runner's record and output for each attempt, and a second run
    leaves a second, never rewriting the first."""

    markers = tmp_path / "markers"
    root, markers = project(tmp_path, [claim(markers, "alpha", 3)], ["alpha"])

    verify(root, "1", capsys=capsys)
    verify(root, "1", capsys=capsys)

    kept = records(root)
    assert [(item["claim"], item["verdict"], item["exit_code"]) for item in kept] == [
        ("alpha", "FAIL", 3)
    ] * 2
    assert len(list((root / CHECKS).glob("alpha.*.out"))) == 2


def test_a_failing_claim_fails_the_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path, [claim(markers, "alpha"), claim(markers, "beta", 3)], ["alpha", "beta"]
    )

    code, out, _ = verify(root, "1", capsys=capsys)

    assert code == 1
    assert "FAIL beta [test, required] — declared check exit 3" in out
    assert lines(out)[-1] == "VERDICT: FAIL (done-when of #1: 1 PASS, 1 FAIL)"


def test_the_ticket_requires_a_claim_the_plan_marks_optional(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`outcomebound validation` passes a plan whose only failing claim is optional; a ticket that
    names that claim requires it, so the verdict is not PASS."""

    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path,
        [claim(markers, "alpha", 3, required=False), claim(markers, "beta")],
        ["alpha"],
    )

    code, out, _ = verify(root, "1", capsys=capsys)

    assert code == 1
    assert "FAIL alpha [test, required]" in out
    assert lines(out)[-1].startswith("VERDICT: FAIL")


def test_a_claim_the_plan_does_not_define_runs_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One missing name stops the run before the defined claims start, names every missing
    claim, and exits as an invalid plan does."""

    markers = tmp_path / "markers"
    root, markers = project(tmp_path, [claim(markers, "alpha")], ["alpha", "ghost", "phantom"])

    code, out, err = verify(root, "1", capsys=capsys)

    assert code == 2
    assert out == ""
    assert err.count("\n") == 1 and err.startswith("CLAIM_MISSING: ")
    assert "ghost, phantom" in err and "alpha" not in err.split("define")[0].split("names")[1]
    assert ran(markers) == set()
    assert not (root / CHECKS).exists()


def test_a_persons_check_is_unverified_and_the_rest_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """On a ticket a person does, the person's check is printed and run by nobody, and it keeps the
    verdict from PASS while the claims of the plan still run."""

    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path,
        [claim(markers, "alpha")],
        ["alpha", "signed-off: human: the notes read correctly"],
        human_only="yes",
    )

    code, out, _ = verify(root, "1", capsys=capsys)

    assert code == 2
    assert ran(markers) == {"alpha"}
    assert "UNVERIFIED signed-off [person's check] — the notes read correctly" in out
    assert lines(out)[-1] == "VERDICT: UNVERIFIED (done-when of #1: 1 PASS, 1 UNVERIFIED)"


def test_a_persons_check_alone_is_never_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no command to run, the verdict is not the runner's empty PASS."""

    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path,
        [claim(markers, "alpha")],
        ["signed-off: human: the notes read correctly"],
        human_only="yes",
    )

    code, out, _ = verify(root, "1", capsys=capsys)

    assert code == 2
    assert ran(markers) == set()
    assert lines(out)[-1] == "VERDICT: UNVERIFIED (done-when of #1: 1 UNVERIFIED)"


def test_a_claim_that_cannot_run_is_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path,
        [claim(markers, "alpha", required_paths=["not-yet-written.txt"])],
        ["alpha"],
    )

    code, out, _ = verify(root, "1", capsys=capsys)

    assert code == 2
    assert "UNVERIFIED alpha" in out and "required path missing" in out
    assert ran(markers) == set()


def test_a_closed_ticket_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    markers = tmp_path / "markers"
    root, markers = project(tmp_path, [claim(markers, "alpha")], ["alpha"], status="closed")

    code, out, err = verify(root, "1", capsys=capsys)

    assert (code, out) == (1, "")
    assert err.startswith("VERIFY_REFUSED: #1 is closed")
    assert ran(markers) == set()


def test_a_ticket_check_reports_an_error_on_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path,
        [claim(markers, "alpha")],
        ["alpha"],
        reads=("docs/specs/example/contracts.md#no-such-section",),
    )

    code, out, err = verify(root, "1", capsys=capsys)

    assert (code, out) == (1, "")
    assert err.startswith("VERIFY_REFUSED: `check` reports an error on #1")
    assert "READS_UNRESOLVED" in err
    assert ran(markers) == set()


def test_a_plan_that_runs_outside_the_checkout_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(tmp_path, [claim(markers, "alpha")], ["alpha"])
    write(root, CLAIMS_PATH, plan_document([claim(markers, "alpha")], cwd="../.."))

    code, out, err = verify(root, "1", capsys=capsys)

    assert (code, out) == (1, "")
    assert err.startswith("VERIFY_REFUSED: the claims plan") and "outside this checkout" in err
    assert ran(markers) == set()


def test_a_plan_the_runner_cannot_load_is_an_invalid_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(
        tmp_path,
        [claim(markers, "alpha"), {"name": "beta", "risk": "r", "kind": "test"}],
        ["alpha"],
    )

    code, out, err = verify(root, "1", capsys=capsys)

    assert (code, out) == (2, "")
    assert err.startswith("PLAN_INVALID: ")
    assert ran(markers) == set()


def test_a_ticket_the_store_lacks_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(tmp_path, [claim(markers, "alpha")], ["alpha"])

    code, out, err = verify(root, "9", capsys=capsys)

    assert (code, out) == (1, "")
    assert err.startswith("TICKET_NOT_FOUND: the declared store holds no ticket #9")
    assert ran(markers) == set()


def test_a_draft_is_verified_from_its_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(tmp_path, [claim(markers, "alpha"), claim(markers, "beta")], ["beta"])
    draft = write(root, "drafts/7.md", draft_document(done_when=("alpha",)))

    code, out, _ = verify(root, "7", "--draft", str(draft), capsys=capsys)

    assert code == 0
    assert ran(markers) == {"alpha"}
    assert lines(out)[-1] == "VERDICT: PASS (done-when of 7: 1 PASS)"


def test_a_draft_and_an_export_do_not_combine(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markers = tmp_path / "markers"
    root, markers = project(tmp_path, [claim(markers, "alpha")], ["alpha"])
    draft = write(root, "drafts/7.md", draft_document())

    with pytest.raises(SystemExit) as stopped:
        verify(root, "7", "--draft", str(draft), "--input", str(exported(root)), capsys=capsys)

    assert stopped.value.code == 2
    assert "--draft" in capsys.readouterr().err
    assert ran(markers) == set()


def test_a_ticket_named_before_the_checkout_gets_the_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no declaration at the folder it was given, `verify` names the order as `brief` does."""

    capsys.readouterr()
    code = main(["verify", "20", str(tmp_path)])
    err = capsys.readouterr().err

    assert code == 1
    assert err.startswith("DECLARATION_MISSING: ")
    assert "`verify` takes the target first, then the ticket" in err
    assert "outcomebound tickets verify" in err


def test_block_keys_are_unchanged_by_the_fixture() -> None:
    """The fixture's block is the one `brief`'s tests read, so a ticket here is a ticket there."""

    assert block(done_when=("alpha",))[4:6] == ["done-when:", "- alpha"]
