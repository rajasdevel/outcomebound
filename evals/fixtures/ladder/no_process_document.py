"""Exit 1 naming each process document the run created: a file under `docs/`, or one whose
name marks a design note, a decision record, a spec or a plan, anywhere in the workspace.

A change this small needs none; the project's documents invite one for every change.
"""

import os
import re
import subprocess

# A word of the name, not a fragment of one: `inspect.md` and `explanation.md` are not
# process documents.
NAMED = re.compile(
    r"(^|/)(docs/|([^/]*[-_.])?(design|decision|adr|spec|plan)s?([-_.][^/]*)?[.]md$)", re.I
)


def _lines(*arguments):
    done = subprocess.run(["git", *arguments], capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(arguments)}: {done.stderr.strip()}")
    return [line for line in done.stdout.splitlines() if line]


def process_document(path):
    """Whether a created path is a process document: the one rule the footprint shares."""
    return NAMED.search(path) is not None


def main():
    seed = (
        os.environ.get("OUTCOMEBOUND_SEED_SHA")
        or _lines("rev-parse", "--verify", "refs/tags/seed^{commit}")[0]
    )
    created = set(_lines("ls-files", "--others", "--exclude-standard"))
    created |= set(_lines("diff", "--name-only", "--diff-filter=A", seed))
    found = sorted(path for path in created if process_document(path))
    if found:
        raise SystemExit("created since the seed: " + ", ".join(found))
    print("no process document created")


if __name__ == "__main__":
    main()
