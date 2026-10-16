#!/usr/bin/env python3
"""Run the suite in the two container images CI runs, on this machine, before a push.

A clean clone of HEAD, with its history and tags, is mounted read-only in each image and copied
onto the container's own file system, where `scripts/container-suite.sh` runs it as CI's
container job does: as root, with no init process, so a child nobody reaps stays a zombie as in
CI. Uncommitted changes are not in the clone. Both images run at once. Arguments go to pytest
(a file or a test to narrow a diagnosis); with none, the whole suite runs. Needs Docker. One line
per image, PASS or FAIL with pytest's summary and each failed test; exit 1 when one fails, or
when Docker cannot run, which reads UNVERIFIED.
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ("python:3.13-slim", "python:3.13-alpine")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
        epilog="\n".join(__doc__.strip().splitlines()[2:]),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pytest", nargs=argparse.REMAINDER, help="arguments passed to pytest")
    # pytest's own options (`-k`, `-x`) pass through as they are.
    known, others = parser.parse_known_args(argv)
    argv = others + known.pytest
    docker = shutil.which("docker")
    if docker is None or subprocess.run([docker, "info"], capture_output=True).returncode != 0:
        print("UNVERIFIED containers: Docker is not running on this machine")
        return 1
    with tempfile.TemporaryDirectory(prefix="outcomebound-containers-") as folder:
        clone = Path(folder) / "clone"
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(clone)], check=True)
        head = subprocess.run(
            ["git", "-C", str(clone), "log", "-1", "--format=%h %s"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.strip()
        print(f"containers: HEAD {head}")
        script = "cp -a /src /w && cd /w && exec sh scripts/container-suite.sh " + shlex.join(argv)
        logs = {image: Path(folder) / f"{image.replace(':', '-')}.log" for image in IMAGES}
        runs = {}
        for image in IMAGES:
            handle = logs[image].open("w", encoding="utf-8")
            runs[image] = (
                subprocess.Popen(
                    [docker, "run", "--rm", "-v", f"{clone}:/src:ro", image, "sh", "-c", script],
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                ),
                handle,
            )
        failed = False
        for image, (process, handle) in runs.items():
            code = process.wait()
            handle.close()
            lines = logs[image].read_text(encoding="utf-8", errors="replace").splitlines()
            summary = next((line for line in reversed(lines) if " in " in line), "no summary")
            failures = [line for line in lines if line.startswith(("FAILED ", "ERROR "))]
            failed = failed or code != 0
            print(f"{'PASS' if code == 0 else 'FAIL'} {image}: {summary}")
            for line in failures:
                print(f"  {line}")
            if code != 0 and not failures:
                print("\n".join(f"  {line}" for line in lines[-20:]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
