#!/usr/bin/env python3
"""Check that a release commit agrees with itself, and with its tag when one is named.

`VERSION`, the dated `CHANGELOG.md` section, its link and the `[Unreleased]` compare link that
starts at it, and the release the README and the
shipped CI template install name one version, on a tree that matches HEAD. With `--tag`, the
tag is `v<VERSION>`, annotated, and on HEAD, and HEAD has a passing CI run on main, so
no release is cut from a main that failed. One line per check; exit 1 when any fails.
`make release-check TAG=v<VERSION>` runs this on the tag made locally, before it is pushed, and CI
runs it again on the tag.

A last line says whether a grant in `.outcomebound/tag-grants.json` lets an agent push the tag
today; it is no check, since a maintainer's own tag needs none.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPOSITORY = "https://github.com/rajasdevel/outcomebound"
CI = "templates/ci"
GITHUB_TEMPLATE = f"{CI}/github-actions.yml"
# An install line's release: `…/outcomebound@v1.2.0`, a pre-release `…@v1.2.0-rc.1` too.
PIN = re.compile(r"/outcomebound@v(\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?)")


def _git(root: Path, *arguments: str) -> str | None:
    done = subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else None


def _pins(root: Path) -> dict[str, list[str]]:
    """Each release an install line names, in the README and every CI template, by file."""

    files = ["README.md", *sorted(f"{CI}/{p.name}" for p in (root / CI).iterdir() if p.is_file())]
    return {name: PIN.findall((root / name).read_text(encoding="utf-8")) for name in files}


API_HOST = "api.github.com"
WORKFLOW = ".github/workflows/ci.yml"
REPOSITORY_NAME = "rajasdevel/outcomebound"
API_PATH = "/repos/rajasdevel/outcomebound"


def ci_runs(head: str, source: Path | None) -> list[dict[str, object]]:
    """The CI runs of `head`, from GitHub (with `GH_TOKEN` or `GITHUB_TOKEN` where set) or, for a
    check with no network, from the JSON file `source` that holds GitHub's answer."""

    if source is not None:
        answer = json.loads(source.read_text(encoding="utf-8"))
    else:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "outcomebound-release-check",
        }
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        connection = http.client.HTTPSConnection(API_HOST, timeout=30)
        try:
            connection.request(
                "GET",
                f"{API_PATH}/actions/workflows/ci.yml/runs?head_sha={head}&branch=main&per_page=100",
                headers=headers,
            )
            response = connection.getresponse()
            body = response.read()
        finally:
            connection.close()
        if response.status != 200:
            raise OSError(f"GitHub answered {response.status}")
        answer = json.loads(body)
    runs = answer.get("workflow_runs", []) if isinstance(answer, dict) else []
    return [run for run in runs if isinstance(run, dict)]


def _repository(run: dict[str, object]) -> str | None:
    """The full name of the repository a run belongs to, or None where the run does not say."""

    repository = run.get("repository")
    name = repository.get("full_name") if isinstance(repository, dict) else None
    return name if isinstance(name, str) else None


def main_ci(head: str, source: Path | None) -> tuple[bool, str]:
    """Whether a run of this repository's CI workflow on main, of a push or started by hand,
    completed and passed on exactly `head`. A run that names another commit, another workflow
    file or no such fields, from GitHub or from a saved file, does not count."""

    if not head:
        return False, "HEAD's CI run on main could not be read: no HEAD commit"
    try:
        runs = ci_runs(head, source)
    except (OSError, ValueError) as error:
        return False, f"HEAD's CI run on main could not be read: {error}"
    on_main = [
        run
        for run in runs
        if run.get("head_sha") == head
        and run.get("path") == WORKFLOW
        and run.get("event") in ("push", "workflow_dispatch")
        and run.get("head_branch") == "main"
        and _repository(run) == REPOSITORY_NAME
    ]
    # The newest completed run decides: an older pass does not outweigh a newer failure.
    completed = sorted(
        (run for run in on_main if run.get("status") == "completed"),
        key=lambda run: str(run.get("created_at") or ""),
    )
    if completed and completed[-1].get("conclusion") == "success":
        return True, "HEAD has a passing CI run on main"
    seen = ", ".join(sorted({str(run.get("conclusion") or run.get("status")) for run in on_main}))
    return False, f"HEAD has no passing CI run on main ({seen or 'none'})"


def unnamed_pulls(root: Path, version: str, changelog: list[str]) -> list[str] | None:
    """The pull requests that landed since the previous release (`(#N)` in a first-parent
    subject) and that the section of `version` does not name; None where no previous release
    tag is found. The release commit itself is not counted: HEAD, where it sets VERSION or its
    subject is `release: <version>`, with or without its pull request's number. The second form
    knows a release cut again, whose VERSION an earlier cut already set."""

    previous = _git(
        root,
        "describe",
        "--tags",
        "--abbrev=0",
        "--match",
        "v*",
        "--exclude",
        f"v{version}",
        "HEAD",
    )
    if not previous:
        return None
    log = _git(root, "log", "--first-parent", "--format=%H%x00%s", f"{previous}..HEAD") or ""
    head = _git(root, "rev-parse", "HEAD")
    subject = _git(root, "log", "-1", "--format=%s", "HEAD") or ""
    release = "VERSION" in (
        _git(root, "diff", "--name-only", "HEAD~1", "HEAD") or ""
    ).split() or bool(re.fullmatch(rf"release: {re.escape(version)}( \(#\d+\))?", subject))
    heading = re.compile(rf"## \[{re.escape(version)}\] - ")
    start = next((i for i, line in enumerate(changelog) if heading.match(line)), None)
    if start is None:
        return []
    end = next(
        (i for i in range(start + 1, len(changelog)) if changelog[i].startswith("## [")),
        len(changelog),
    )
    section = "\n".join(changelog[start:end])
    numbers = [
        number
        for commit, _, subject in (line.partition("\x00") for line in log.splitlines())
        if not (release and commit == head)
        for number in re.findall(r"\(#(\d+)\)$", subject)
    ]
    return [f"#{number}" for number in numbers if not re.search(rf"#{number}\b", section)]


def checks(root: Path, tag: str | None, runs: Path | None = None) -> list[tuple[bool, str]]:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    pins = _pins(root)
    stale = [
        f"{name} pins v{found}"
        for name, found_all in pins.items()
        if name not in ("README.md", GITHUB_TEMPLATE)
        for found in found_all
        if found != version
    ]
    dated = re.compile(rf"## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}")
    results = [
        (
            _git(root, "status", "--porcelain", "--untracked-files=no") == "",
            "the tree matches HEAD",
        ),
        (
            any(dated.fullmatch(line) for line in changelog),
            f"CHANGELOG.md has a dated {version} section",
        ),
        (
            f"[{version}]: {REPOSITORY}/releases/tag/v{version}" in changelog,
            f"CHANGELOG.md links {version} to its tag",
        ),
        (
            f"[Unreleased]: {REPOSITORY}/compare/v{version}...HEAD" in changelog,
            f"CHANGELOG.md compares Unreleased from v{version}",
        ),
        (
            pins.get(GITHUB_TEMPLATE, []) != [] and set(pins[GITHUB_TEMPLATE]) == {version},
            f"{GITHUB_TEMPLATE} pins v{version}",
        ),
        (
            pins.get("README.md", []) != [] and set(pins["README.md"]) == {version},
            f"README.md installs v{version}",
        ),
        (not stale, "every other install line pins it" + "".join(f"; {line}" for line in stale)),
    ]
    unnamed = unnamed_pulls(root, version, changelog)
    what = f"CHANGELOG.md's {version} section names each pull request since the previous release"
    if unnamed is None:
        # No release tag below this version in this clone (a shallow clone, or the first
        # release): nothing to compare, which is not a pass.
        results.append((False, f"{what}: UNVERIFIED, no previous release tag in this clone"))
    else:
        results.append(
            (not unnamed, what + (f"; not named: {', '.join(unnamed)}" if unnamed else ""))
        )
    if tag is not None:
        head = _git(root, "rev-parse", "HEAD")
        results += [
            (tag == f"v{version}", f"the tag {tag} names VERSION {version}"),
            (_git(root, "cat-file", "-t", f"refs/tags/{tag}") == "tag", f"{tag} is annotated"),
            (
                head is not None and _git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}") == head,
                f"{tag} points at HEAD",
            ),
            main_ci(head or "", runs),
        ]
    return results


def grant(root: Path, today: date) -> str:
    """Name the grant that lets an agent push v<VERSION> today, or say that none does."""

    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    try:
        grants = json.loads((root / ".outcomebound/tag-grants.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        grants = {}
    for entry in grants.get("grants", []):
        scope = str(entry.get("scope", ""))
        covered = version == scope or (
            scope.endswith(".x") and version.startswith(scope[:-1]) and "-" not in version
        )
        if covered and today.isoformat() <= str(entry.get("until", "")):
            return (
                f"GRANT v{version}: {entry.get('granted_by')} granted {scope} on "
                f"{entry.get('on')}, until {entry.get('until')}; an agent may push the tag once "
                "every check above passes"
            )
    return f"GRANT none covers v{version}: pushing the tag is a maintainer's act"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="the release tag to check as well, e.g. v1.0.0")
    parser.add_argument("--root", type=Path, default=Path("."), help="the checkout (default .)")
    parser.add_argument(
        "--ci-runs",
        type=Path,
        help="with --tag: a JSON file holding GitHub's list of HEAD's CI runs, read in place of "
        "GitHub, for a check with no network",
    )
    args = parser.parse_args(argv)
    results = checks(args.root, args.tag, args.ci_runs)
    for passed, what in results:
        print(f"{'PASS' if passed else 'FAIL'} {what}")
    print(grant(args.root, date.today()))
    return 0 if all(passed for passed, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
