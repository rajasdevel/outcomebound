#!/usr/bin/env python3
"""Check that a release commit agrees with itself, and with its tag when one is named.

`VERSION`, the dated `CHANGELOG.md` section and its link, and the release the README and the
shipped CI template install name one version, on a tree that matches HEAD. With `--tag`, the
tag is `v<VERSION>`, annotated, and on HEAD. One line per check; exit 1 when any fails.
`make release-check` runs this before the tag is pushed, and CI runs it again on the tag.

A last line says whether a grant in `.outcomebound/tag-grants.json` lets an agent push the tag
today; it is no check, since a maintainer's own tag needs none.
"""

from __future__ import annotations

import argparse
import json
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


def checks(root: Path, tag: str | None) -> list[tuple[bool, str]]:
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
            pins.get(GITHUB_TEMPLATE, []) != [] and set(pins[GITHUB_TEMPLATE]) == {version},
            f"{GITHUB_TEMPLATE} pins v{version}",
        ),
        (
            pins.get("README.md", []) != [] and set(pins["README.md"]) == {version},
            f"README.md installs v{version}",
        ),
        (not stale, "every other install line pins it" + "".join(f"; {line}" for line in stale)),
    ]
    if tag is not None:
        head = _git(root, "rev-parse", "HEAD")
        results += [
            (tag == f"v{version}", f"the tag {tag} names VERSION {version}"),
            (_git(root, "cat-file", "-t", f"refs/tags/{tag}") == "tag", f"{tag} is annotated"),
            (
                head is not None and _git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}") == head,
                f"{tag} points at HEAD",
            ),
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
    args = parser.parse_args(argv)
    results = checks(args.root, args.tag)
    for passed, what in results:
        print(f"{'PASS' if passed else 'FAIL'} {what}")
    print(grant(args.root, date.today()))
    return 0 if all(passed for passed, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
