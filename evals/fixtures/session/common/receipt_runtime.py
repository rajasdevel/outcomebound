"""Runtime receipts for the synthetic workspace's checks and local ref updates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat()


def root():
    return Path(__file__).resolve().parents[1]


def git(*args):
    done = subprocess.run(
        ["git", *args],
        cwd=root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def write(kind, name, started, status, **facts):
    if os.environ.get("OB_RECEIPTS_DISABLED"):
        return
    git_dir = git("rev-parse", "--git-common-dir")
    if not git_dir:
        return
    folder = root() / git_dir / "ob-receipts"
    folder.mkdir(parents=True, exist_ok=True)
    content = facts.get("inputs", {})
    row = {
        "kind": kind,
        "name": name,
        "started_at": started,
        "ended_at": stamp(),
        "exit_code": status if status == "unknown" else int(status),
        "revision": git("rev-parse", "HEAD"),
        "workspace": str(root()),
        "argv": list(getattr(sys, "orig_argv", sys.argv)),
        "inputs": content,
        "digest": hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(),
        **facts,
    }
    with (folder / f"{os.getpid()}-{time.time_ns()}.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")


def entry(name):
    path = root() / name
    content = {name: hashlib.sha256(path.read_bytes()).hexdigest()}
    write("check", name, stamp(), "unknown", inputs=content)


def ref_update():
    if sys.argv[1:] != ["committed"]:
        return
    started = stamp()
    repository = subprocess.run(
        ["git", "rev-parse", "--is-bare-repository"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    remote = (
        {"true": True, "false": False}.get(repository.stdout.strip())
        if repository.returncode == 0
        else None
    )
    for line in sys.stdin:
        old, new, ref = line.split()
        if ref.startswith(("refs/heads/", "refs/tags/")):
            write(
                "ref",
                ref,
                started,
                0,
                old=old,
                new=new,
                remote=remote,
            )


def observe(argv):
    """Observe a process without rewriting its code or inferring a wider test selection."""
    started = stamp()
    # Bind the invocation to a conservative snapshot of its available inputs. This covers
    # non-Python children too. A change during the run leaves the receipt uncredited.
    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    content = {
        name: hashlib.sha256((root() / name).read_bytes()).hexdigest()
        for name in names
        if name and (root() / name).is_file()
    }
    env = {**os.environ, "OB_RECEIPTS_DISABLED": "1"}
    done = subprocess.run(
        argv, cwd=root(), env=env, check=False, capture_output=True, text=True, encoding="utf-8"
    )
    print(done.stdout, end="")
    print(done.stderr, end="", file=sys.stderr)
    tests = re.search(r"Ran (\d+) tests?|(\d+) passed", done.stdout + done.stderr)
    observed_tests = (
        int(next(value for value in tests.groups() if value is not None)) if tests else 0
    )
    unchanged = all(
        (root() / name).is_file()
        and hashlib.sha256((root() / name).read_bytes()).hexdigest() == digest
        for name, digest in content.items()
    )
    write(
        "process",
        Path(argv[0]).name,
        started,
        done.returncode if unchanged else "unknown",
        argv=argv,
        tests=observed_tests,
        inputs=content,
        digest=hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(),
    )
    return done.returncode


if __name__ == "__main__":
    if sys.argv[1:2] == ["observe"]:
        raise SystemExit(observe(sys.argv[2:]))
    ref_update()
