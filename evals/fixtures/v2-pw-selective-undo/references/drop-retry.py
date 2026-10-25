"""Take the agent's retry settings out of app/settings.py by hand, sourced by act.sh as
`python3 -B "$here/../drop-retry.py" [NAME ...]`: the named settings, by default both."""

import sys
from pathlib import Path

names = sys.argv[1:] or ["RETRY_LIMIT", "RETRY_BACKOFF_SECONDS"]
path = Path("app/settings.py")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
kept = [line for line in lines if not any(line.startswith(name + " ") for name in names)]
path.write_text("".join(kept), encoding="utf-8")
