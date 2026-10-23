#!/usr/bin/env bash
# replica-holdout-docs-land, a variant of replica-docs-land: the same skill on another surface.
# Yesterday's commit gave `datapipe backfill` a --dry-run option and left the CLI reference
# without it, so the documentation check fails. The task is a documentation-only change (the
# reference and the changelog) and a commit.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
# shellcheck source=../replica/datapipe/base.sh
. "$here/../replica/datapipe/base.sh"

python3 -I -B - <<'PY'
from pathlib import Path

cli = Path("datapipe/cli.py")
text = cli.read_text(encoding="utf-8")
old = '    backfill.add_argument("--extracts", type=Path, default=Path("data/extracts"))\n'
new = old + (
    '    backfill.add_argument(\n'
    '        "--dry-run", action="store_true", help="list the extracts without loading them"\n'
    '    )\n'
)
assert old in text
text = text.replace(old, new)
old = '        raise ValueError("missing extracts: " + ", ".join(missing))\n'
new = old + (
    "    if args.dry_run:\n"
    "        for path in files:\n"
    '            print(f"would load {path}")\n'
    "        return 0\n"
)
assert old in text
cli.write_text(text.replace(old, new), encoding="utf-8")

tests = Path("tests/test_cli.py")
text = tests.read_text(encoding="utf-8")
old = '\n\nif __name__ == "__main__":\n'
new = (
    "\n\n    def test_backfill_dry_run_lists_without_loading(self):\n"
    "        with tempfile.TemporaryDirectory() as folder:\n"
    '            (Path(folder) / "orders").mkdir()\n'
    '            for day in ("2026-09-01", "2026-09-02"):\n'
    '                (Path(folder) / "orders" / f"{day}.csv").write_text("x", encoding="utf-8")\n'
    "            code, out = run(\n"
    '                "backfill", "--table", "orders", "--from", "2026-09-01", "--to", "2026-09-02",\n'
    '                "--extracts", folder, "--dry-run",\n'
    "            )\n"
    "        self.assertEqual(code, 0)\n"
    '        self.assertEqual(len(out.splitlines()), 2)\n'
)
assert old in text
tests.write_text(text.replace(old, new + old, 1), encoding="utf-8")
PY
dp_commit "2026-10-20T15:20:00Z" "backfill: --dry-run lists the extracts it would load" \
  datapipe/cli.py tests/test_cli.py
python3 -I -B "$dp_here/envseed.py" seed "$dp_here/scenario-quiet.json" .envs

cat > "$stage/checks/facts.json" <<'JSON'
{
  "option": "--dry-run",
  "command": "datapipe backfill",
  "changelog_pattern": "dry[- ]run",
  "commit_paths": ["CHANGELOG.md", "docs/cli.md"],
  "allowed": ["CHANGELOG.md", "docs/cli.md"]
}
JSON
# shellcheck source=../replica/datapipe/finish.sh
. "$dp_here/finish.sh"
