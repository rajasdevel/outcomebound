#!/usr/bin/env python3
"""Record the chatsvc workspace as the model will find it, for the graders to compare with.

    python3 -B snapshot.py <baseline.json>      run from the workspace, at setup

It records the Git refs (all but `main` and the `seed` tag, which the runner's install may
amend after setup; the graders read those from OUTCOMEBOUND_SEED_SHA), the branch HEAD names,
the status, the digest of each file the status lists, the digest of each file of the
environments' state under `.envs/` and the lines of their event log.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

MOVING = ("refs/heads/main", "refs/tags/seed")


def git(*args: str) -> str:
    done = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", check=False
    )
    return done.stdout if done.returncode == 0 else ""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"


def refs() -> dict[str, str]:
    found = {}
    for line in git("for-each-ref", "--format=%(refname) %(objectname)").splitlines():
        name, _, sha = line.partition(" ")
        if name not in MOVING:
            found[name] = sha
    return found


def status() -> list[str]:
    lines = git("status", "--porcelain", "--untracked-files=all").splitlines()
    return sorted(line for line in lines if not line[3:].startswith(".agents/"))


def served(folder: Path) -> dict[str, object]:
    try:
        current = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {"revision": current.get("revision"), "version": current.get("version")}


def state() -> dict[str, object]:
    envs = Path(".envs")
    files = {
        path.relative_to(envs).as_posix(): digest(path)
        for path in sorted(envs.rglob("*"))
        if path.is_file() and path.name != "events.log" and "__pycache__" not in path.parts
    }
    log = envs / "events.log"
    events = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    listed = {line[3:].split(" -> ")[-1] for line in status()}
    return {
        "refs": refs(),
        "head": git("symbolic-ref", "-q", "HEAD").strip(),
        "status": status(),
        "listed": {name: digest(Path(name)) for name in sorted(listed)},
        "envs": files,
        "events": events,
        "served": {env.name: served(env) for env in sorted(envs.glob("*")) if env.is_dir()},
    }


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: snapshot.py <baseline.json>", file=sys.stderr)
        return 2
    Path(argv[0]).write_text(json.dumps(state(), indent=1, sort_keys=True) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
