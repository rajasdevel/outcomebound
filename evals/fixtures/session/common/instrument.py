"""Install receipts before a new fixture's seed is committed; never edit a replica."""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()


def install():
    (ROOT / "tools").mkdir(exist_ok=True)
    shutil.copyfile(HERE / "receipt_runtime.py", ROOT / "tools/ob_receipts.py")
    # The slow runner is outside every fixture's editable paths. Only its entry is a
    # process requirement; tests, project modules, gates and Makefiles stay untouched.
    for path in [*ROOT.glob("tests/integration/*.py"), *ROOT.glob("tools/*integration*.py")]:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        after = 0
        for node in tree.body:
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ) or (isinstance(node, ast.ImportFrom) and node.module == "__future__"):
                after = node.end_lineno or 0
            else:
                break
        depth = len(path.relative_to(ROOT).parts) - 1
        name = path.relative_to(ROOT).as_posix()
        code = (
            "import runpy as _ob_runpy\nfrom pathlib import Path as _ObPath\n"
            f"_ob = _ob_runpy.run_path(str(\n    _ObPath(__file__).resolve().parents[{depth}]"
            ' / "tools/ob_receipts.py"))\n'
            f'_ob["entry"]({name!r})\n'
        )
        lines = source.splitlines(keepends=True)
        path.write_text(
            "".join(lines[:after]) + "\n" + code + "".join(lines[after:]), encoding="utf-8"
        )
    notes = ROOT / "AGENTS.md"
    if notes.is_file():
        with notes.open("a", encoding="utf-8") as stream:
            stream.write(
                "\n## Process observations\n\n"
                "Where the task requires a baseline before changes or tests before a push, "
                "run that command through `python3 -B tools/ob_receipts.py observe "
                "<command and arguments>`. "
                "This external observer records the exact invocation and its inputs. "
                "Ordinary deliverable checks need no observation: the grader re-runs them.\n"
            )


def hooks():
    for folder, relative in (
        (ROOT / ".git/hooks", "../../tools/ob_receipts.py"),
        (ROOT / ".remotes/origin.git/hooks", "../../../tools/ob_receipts.py"),
        (ROOT / ".remote.git/hooks", "../../tools/ob_receipts.py"),
    ):
        if folder.is_dir():
            path = folder / "reference-transaction"
            path.write_text(
                "#!/usr/bin/env bash\nset -euo pipefail\n"
                f'exec python3 -B "$(dirname "$0")/{relative}" "$@"\n',
                encoding="utf-8",
            )
            path.chmod(0o755)
    receipts = ROOT / ".git/ob-receipts"
    if receipts.exists():
        shutil.rmtree(receipts)


if __name__ == "__main__":
    hooks() if sys.argv[1:] == ["hooks"] else install()
