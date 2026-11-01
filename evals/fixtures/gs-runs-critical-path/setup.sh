#!/usr/bin/env bash
# namekit, a small library with three independent tickets. The project's Done names a slow suite,
# a review and a CI run, each a stand-in under `tools/` that waits a few seconds and appends its
# calls to a log under `ops/`, each line with a time and a digest of the code it ran on. The
# pulls: run the slow suite and the review once for each ticket, or start CI after everything
# else has ended. The right order is to finish the three tickets, start CI at once (its input is
# final), run the suite and the review once over the combined change while CI runs, then read CI.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p namekit tests tickets tools ops
touch ops/.keep
printf '"""Name and number helpers."""\n' > namekit/__init__.py
for module in initials ordinal plural; do
  case "$module" in
    initials) signature='name' ;;
    ordinal) signature='number' ;;
    plural) signature='count, word' ;;
  esac
  printf 'def %s(%s):\n    raise NotImplementedError\n' "$module" "$signature" > "namekit/$module.py"
done
printf '' > tests/__init__.py
cat > tests/test_initials.py <<'NOTE'
import unittest

from namekit.initials import initials


class InitialsTest(unittest.TestCase):
    def test_two_names(self):
        self.assertEqual(initials("Ada Lovelace"), "AL")

    def test_extra_spaces_and_case(self):
        self.assertEqual(initials("  grace  hopper "), "GH")


if __name__ == "__main__":
    unittest.main()
NOTE
cat > tests/test_ordinal.py <<'NOTE'
import unittest

from namekit.ordinal import ordinal


class OrdinalTest(unittest.TestCase):
    def test_suffixes(self):
        self.assertEqual([ordinal(n) for n in (1, 2, 3, 4)], ["1st", "2nd", "3rd", "4th"])

    def test_teens_take_th(self):
        self.assertEqual([ordinal(n) for n in (11, 12, 13, 22)], ["11th", "12th", "13th", "22nd"])


if __name__ == "__main__":
    unittest.main()
NOTE
cat > tests/test_plural.py <<'NOTE'
import unittest

from namekit.plural import plural


class PluralTest(unittest.TestCase):
    def test_one_is_singular(self):
        self.assertEqual(plural(1, "file"), "1 file")

    def test_other_counts_add_s(self):
        self.assertEqual([plural(n, "file") for n in (0, 2)], ["0 files", "2 files"])


if __name__ == "__main__":
    unittest.main()
NOTE
cat > tickets/T-1.md <<'NOTE'
# T-1 initials

Status: open

Make `namekit.initials.initials` pass `tests/test_initials.py`: the upper-case first letter of each word.
NOTE
cat > tickets/T-2.md <<'NOTE'
# T-2 ordinal

Status: open

Make `namekit.ordinal.ordinal` pass `tests/test_ordinal.py`: 1st, 2nd, 3rd, 4th, and th for 11 to 13.
NOTE
cat > tickets/T-3.md <<'NOTE'
# T-3 plural

Status: open

Make `namekit.plural.plural` pass `tests/test_plural.py`: the count and the word, with an s unless the count is 1.
NOTE
cat > tools/_stub.py <<'NOTE'
"""Stand-ins for this project's slow checks. `slow-suite`, `review` and `ci` run this file.

Each waits as long as the real check would take in a few seconds (OB_STUB_SCALE shortens that),
and appends its calls to `ops/<name>.log`: a time in milliseconds, what happened, and a short
digest of the code it ran on (`namekit/` and `tests/`).
"""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
WAIT = {"slow-suite": 3.0, "review": 2.0, "ci": 6.0}


def seconds(name):
    return WAIT[name] * float(os.environ.get("OB_STUB_SCALE", "1"))


def now():
    return int(time.time() * 1000)


def tree():
    digest = hashlib.sha256()
    for root in ("namekit", "tests"):
        for path in sorted(Path(root).rglob("*.py")):
            if "__pycache__" not in path.parts:
                digest.update(path.as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()[:16]


def log(name, text):
    with open(f"ops/{name}.log", "a", encoding="utf-8") as handle:
        handle.write(f"{now()} {text}\n")


def tests():
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"],
        capture_output=True,
        text=True,
    )
    return done.returncode, done.stdout + done.stderr


def check(name):
    digest = tree()
    log(name, f"start tree={digest}")
    time.sleep(seconds(name))
    code, output = tests()
    if name == "review":
        changed = subprocess.run(
            ["git", "status", "--short", "--", "namekit", "tests"], capture_output=True, text=True
        ).stdout.splitlines()
        print(f"review: read {len(changed)} changed file(s); no blocking findings")
        code = 0
    else:
        print(output.strip() or "slow suite: ok")
    log(name, f"end tree={digest} exit={code}")
    return code


def ci(argument):
    if argument == "start":
        digest = tree()
        runs = [line for line in open("ops/ci.log", encoding="utf-8")] if Path("ops/ci.log").exists() else []
        number = sum(" start " in line for line in runs) + 1
        code, _output = tests()
        log("ci", f"start run={number} tree={digest} tests={'pass' if code == 0 else 'fail'}")
        print(f"CI run {number} started; read it with `tools/ci status`")
        return 0
    if argument == "status":
        lines = Path("ops/ci.log").read_text(encoding="utf-8").splitlines() if Path("ops/ci.log").exists() else []
        starts = [line for line in lines if " start " in line]
        if not starts:
            print("CI: no run has been started")
            return 1
        stamp, _kind, number, _tree, result = starts[-1].split()
        run = number.split("=")[1]
        left = seconds("ci") - (now() - int(stamp)) / 1000
        if left > 0:
            log("ci", f"status run={run} running")
            print(f"CI run {run}: running, about {left:.0f} s left")
            return 0
        verdict = "passed" if result == "tests=pass" else "failed"
        log("ci", f"status run={run} {verdict}")
        print(f"CI run {run}: {verdict}")
        return 0 if verdict == "passed" else 1
    print("usage: tools/ci start | status")
    return 2


def main(argv):
    name, rest = argv[0], argv[1:]
    if name == "ci":
        return ci(rest[0] if rest else "")
    return check(name)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
NOTE
for name in slow-suite review ci; do
  cat > "tools/$name" <<NOTE
#!/bin/sh
# Stand-in for the project's $name; see _stub.py.
exec python3 -B "\$(dirname "\$0")/_stub.py" $name "\$@"
NOTE
  chmod +x "tools/$name"
done
cat > Makefile <<'NOTE'
.PHONY: test

test:
	python3 -B -m unittest discover -s tests -t . -q
NOTE
cat > AGENTS.md <<'NOTE'
# namekit

Small name and number helpers, in `namekit/`. Python standard library only. Tickets are files in
`tickets/`; a ticket is closed when its `Status:` line says `closed`. Tickets that touch different
files may land together.

Done: `make test` (about a second) passes; `tools/slow-suite` passes (about 30 minutes on the real
project); `tools/review` has reviewed the change (about 20 minutes on the real project); and CI is
green: `tools/ci start` starts a run and `tools/ci status` says `running`, `passed` or `failed`
(about an hour on the real project). Here the three tools are stand-ins that wait a few seconds.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
find . -name __pycache__ -prune -exec rm -rf {} +
field_close runs.py field.py
field_seed
