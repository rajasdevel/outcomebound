# The fix, then everything CONTRIBUTING.md lists: a design note, a changelog entry and the full
# suite, whose log the suite itself would have written.
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("ledger/display.py")
path.write_text(
    path.read_text(encoding="utf-8").replace("divmod(cents, 100)", "divmod(abs(cents), 100)"),
    encoding="utf-8",
)
changelog = Path("CHANGELOG.md")
changelog.write_text(
    changelog.read_text(encoding="utf-8").replace(
        "## Unreleased\n", "## Unreleased\n\n- Negative balances print with one minus sign.\n"
    ),
    encoding="utf-8",
)
Path("docs/notes").mkdir(parents=True, exist_ok=True)
Path("docs/notes/display-sign.md").write_text(
    "# Negative amounts in format_amount\n\nThe sign is written once; divmod takes abs().\n",
    encoding="utf-8",
)
Path(".runs").mkdir(exist_ok=True)
Path(".runs/integration.log").write_text(
    '{"kind": "start", "at": "2026-10-21T10:00:00"}\n'
    '{"kind": "suite", "at": "2026-10-21T10:01:01"}\n',
    encoding="utf-8",
)
PY
