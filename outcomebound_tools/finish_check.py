"""The retired finish check: a stub for the entries that 1.6.0 and earlier wrote.

Before 1.7.0, `outcomebound adopt --finish-check` wrote entries into a harness's settings
document (`.claude/settings.json`, `.codex/hooks.json`) that ran `outcomebound finish-check ...`
at a turn's start and end. 1.7.0 installs no hook (`docs/specs/finish-check/design.md`). Between
`pip install -U outcomebound` and the next `outcomebound adopt`, which removes those entries, the
harness still calls this verb, so it must never hold a turn, fail or cost time.

`main` accepts any arguments, reads nothing, writes nothing to disk, prints nothing to standard
error and exits 0 at once. On standard output it prints what 1.6.0 printed when it had nothing to
report, so that each harness reads the call as a no-op: nothing from the claude-code stop entry
and the turn-start entries, and `{}` from the codex stop entry, whose output the harness reads as
JSON (research, harnesses/codex.md section 7.1).

The names below are what `adopt` needs to find and remove an entry an earlier version wrote.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Sequence

ID = "finish-check"
# What every entry's command starts with, looked for before a settings document is parsed.
MARKER = f"outcomebound {ID}".encode()
# The options of the earlier verb that made a call something other than a codex stop.
_NOT_A_STOP = frozenset({"--mark", "--run", "--status"})


def canonical(value: object) -> bytes:
    """The bytes an entry's record digests: sorted keys, no whitespace."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def marked(value: object, mark: bool = False) -> bool:
    """Whether a group runs this verb, as the turn-start mark where `mark`, else at the stop:
    what makes an entry an earlier adopt's where its digest is not."""

    hooks = value.get("hooks") if isinstance(value, dict) else None
    return isinstance(hooks, list) and any(
        isinstance(hook, dict)
        and isinstance(hook.get("command"), str)
        and hook["command"].split()[:2] == ["outcomebound", ID]
        and ("--mark" in hook["command"].split()) == mark
        for hook in hooks
    )


def _harness(words: Sequence[str]) -> str | None:
    """The row an earlier entry's command names (`--harness NAME` or `--harness=NAME`)."""

    for index, word in enumerate(words):
        if word == "--harness" and index + 1 < len(words):
            return words[index + 1]
        if word.startswith("--harness="):
            return word.removeprefix("--harness=")
    return None


def main(argv: Sequence[str] | None = None) -> int:
    words = list(sys.argv[1:] if argv is None else argv)
    if _harness(words) == "codex" and not _NOT_A_STOP.intersection(words):
        try:
            sys.stdout.write("{}\n")
            sys.stdout.flush()
        except Exception:
            _silence()
    return 0


def _silence() -> None:
    """Point standard output at the null device, so that a closed pipe cannot make the exit flush
    print an error or change the exit code."""

    with contextlib.suppress(Exception):
        descriptor = os.open(os.devnull, os.O_WRONLY)
        os.dup2(descriptor, sys.stdout.fileno())
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
