#!/usr/bin/env python3
"""Run Ponytail's agentic benchmark with an OutcomeBound arm, from a pinned clone.

Ponytail (https://github.com/DietrichGebert/ponytail, MIT, by DietrichGebert) ships its own
benchmark, `benchmarks/agentic/run.py`. This driver never copies it: it makes a fresh worktree of
a pinned clone, applies `ob-arm.patch` (the `ob` arm and the isolation fixes), and checks that
copy before any model call.

  driver.py prepare --clone PATH --commit SHA --out WORKTREE
      A detached worktree of the clone at SHA, with the patch applied. `git apply --check` runs
      first; if the patch does not apply, the worktree is removed and nothing else happens.

  driver.py selftest --worktree WORKTREE [--template PATH]
      Ponytail's own `--selftest` (no API call), then each of our completion oracles
      (checks.py) on its passing and failing reference, through the patched `score_workspace`.

  driver.py dry-run --worktree WORKTREE --clone PATH --commit SHA --tasks IDS --arms IDS
                    [--template PATH] [--out DIR]
      The patched harness builds every cell exactly as a real run would, and records each
      cell's command and environment instead of starting claude. A guard in this process
      refuses any process whose program is claude. Then the checks below run on every cell.

A real run (`run.py --pinned-plugin ponytail=CLONE --ob-launcher ... --ob-checks ...` without
--dry-run) spends model quota and is never started by this driver.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PATCH = HERE / "ob-arm.patch"
CHECKS = HERE / "checks.py"
LAUNCHER = REPO / "scripts" / "outcomebound"
AGENTIC = Path("benchmarks") / "agentic"

# What a cell's environment may hold: Ponytail's run.py builds it from these lists and the
# fresh folders under the cell; anything else is a leak.
FRESH = (
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "CLAUDE_CONFIG_DIR",
    "TMPDIR",
)
OB_FILES = (
    "AGENTS.md",
    ".outcomebound/manifest.json",
    ".claude/skills/using-outcomebound/SKILL.md",
)
# Instruction and settings files Claude Code reads from a project; none may appear in a cell
# unless the task seeded it (the ob arm's AGENTS.md and skills are its install).
PROJECT_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CLAUDE.local.md",
    ".claude/CLAUDE.md",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/skills",
    ".outcomebound",
    ".mcp.json",
)
SYNTHETIC_LINES = 7
# The Ponytail commit ob-arm.patch is written against.
PINNED = "09c434ab73ca43761c5d8b0c5d341926c2fba710"


def evals_home() -> Path:
    """The evals home, a local folder of third-party clones: OB_EVALS_HOME, else
    `outcomebound-evals` beside the main checkout."""
    if os.environ.get("OB_EVALS_HOME"):
        return Path(os.environ["OB_EVALS_HOME"])
    common = _git(
        "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=REPO
    ).stdout.strip()
    return Path(common).parent.parent / "outcomebound-evals"


def default_clone() -> Path:
    return Path(os.environ.get("OB_PONYTAIL_CLONE") or evals_home() / "third-party" / "ponytail")


def _git(*args: str, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, env=env, encoding="utf-8"
    )
    if check and done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {(done.stdout + done.stderr).strip()}")
    return done


def _head(path: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=path).stdout.strip()


# ---------------------------------------------------------------- prepare


def prepare(clone: Path, commit: str, out: Path, patch: Path = PATCH) -> Path:
    clone, out = clone.resolve(), out.resolve()
    if _git("cat-file", "-e", f"{commit}^{{commit}}", cwd=clone).returncode != 0:
        raise SystemExit(
            f"prepare: commit {commit} is not in the clone {clone}; git fetch there first"
        )
    if out.exists():
        raise SystemExit(f"prepare: {out} exists; give a new folder")
    _git("worktree", "add", "--detach", str(out), commit, cwd=clone, check=True)
    checked = _git("apply", "--check", str(patch), cwd=out)
    if checked.returncode != 0:
        _git("worktree", "remove", "--force", str(out), cwd=clone)
        raise SystemExit(
            f"prepare: {patch.name} does not apply to {commit}; stopped before anything ran.\n"
            f"{checked.stderr.strip()}\nUpstream changed what the patch touches: "
            "update the patch, or pin the old commit."
        )
    _git("apply", str(patch), cwd=out, check=True)
    print(f"prepared {out} at {commit} with {patch.name}")
    return out


def _prepared(worktree: Path, commit: str | None = None) -> None:
    if not (worktree / AGENTIC / "run.py").is_file():
        raise SystemExit(f"{worktree} is not a Ponytail worktree")
    if commit and _head(worktree) != commit:
        raise SystemExit(f"{worktree} is at {_head(worktree)}, not {commit}")
    if _git("apply", "--reverse", "--check", str(PATCH), cwd=worktree).returncode != 0:
        raise SystemExit(
            f"{worktree} does not hold {PATCH.name} as this checkout has it; prepare a new worktree"
        )


# ---------------------------------------------------------------- the patched harness, in process


class ClaudeRefused(RuntimeError):
    pass


def _guard_claude() -> None:
    """Make this process refuse to start claude: every subprocess goes through Popen."""
    real = shutil.which("claude")
    base = subprocess.Popen
    if getattr(base, "_ob_guard", False):
        return

    class NoClaude(base):  # type: ignore[misc, valid-type]
        _ob_guard = True

        def __init__(self, args, *rest, **kwargs):
            argv0 = str(args[0] if isinstance(args, (list, tuple)) else str(args).split()[0])
            if Path(argv0).name.lower().startswith("claude") or (
                real and os.path.realpath(argv0) == os.path.realpath(real)
            ):
                raise ClaudeRefused(f"refused: this would start {argv0}")
            super().__init__(args, *rest, **kwargs)

    subprocess.Popen = NoClaude  # type: ignore[misc]


def load_harness(worktree: Path, template: Path | None = None):
    """Import the patched run.py with our checks loaded. PONYTAIL_TMPL is set for this process
    only (tasks.py reads it at import); no cell inherits it."""
    _guard_claude()
    if template:
        os.environ["PONYTAIL_TMPL"] = str(template.resolve())
    agentic = str((worktree / AGENTIC).resolve())
    if agentic not in sys.path:
        sys.path.insert(0, agentic)
    sys.modules.pop("tasks", None)
    pt: Any = _load("ponytail_run", Path(agentic) / "run.py")
    pt.OB_CHECKS = pt._load_ob_checks(str(CHECKS))
    pt.OB_LAUNCHER = str(LAUNCHER)
    return pt


def _load(name: str, path: Path) -> ModuleType:
    """The Python file at `path`, imported as module `name`."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checks():
    return _load("ob_ponytail_checks", CHECKS)


def _fixture_ok(pt, task_id: str) -> bool:
    fx = pt.TASKS[task_id].get("fixture")
    if not fx:
        return True
    path = (
        Path(fx)
        if Path(fx).is_absolute()
        else pt.Path(pt.__file__).resolve().parent / "fixtures" / fx
    )
    return path.is_dir()


# ---------------------------------------------------------------- selftest


def selftest(worktree: Path, template: Path | None = None) -> int:
    _prepared(worktree)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PONYTAIL_")}
    up = subprocess.run(
        [sys.executable, "-E", "-s", "run.py", "--selftest"],
        cwd=worktree / AGENTIC,
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
    )
    last = (up.stdout.strip().splitlines() or [""])[-1]
    print(f"{'ok ' if up.returncode == 0 else 'XX '} upstream --selftest: {last}")
    failures = 0 if up.returncode == 0 else 1
    pt = load_harness(worktree, template)
    checks = _checks()
    for task_id, refs in checks.REFERENCES.items():
        if not _fixture_ok(pt, task_id):
            print(
                f"-- {task_id:20} UNVERIFIED: the template fixture is not present (--template PATH)"
            )
            continue
        for kind in ("good", "bad"):
            with tempfile.TemporaryDirectory(prefix="ob-ponytail-ref-") as tmp:
                ws = Path(tmp) / "cell" / "ws"
                ws.mkdir(parents=True)
                pt._build_cell(task_id, "baseline", ws)
                checks.apply_reference(ws, refs[kind])
                r = pt.score_workspace(task_id, "baseline", "ref", ws)
            ok = (
                r["correct"] == (1 if kind == "good" else 0)
                and "oracle" in r
                and "undecided" not in r["oracle"]
            )
            print(
                f"{'ok ' if ok else 'XX '} {task_id:20} {kind:4} correct={r['correct']} "
                f"upstream={r.get('correct_upstream')}  {r.get('oracle')}"
            )
            failures += 0 if ok else 1
    print(f"\nselftest: {'all instruments valid' if not failures else str(failures) + ' BROKEN'}")
    return failures


# ---------------------------------------------------------------- dry run and its checks


def check_env(env: dict, cell: Path) -> list[str]:
    """Problems with a cell's recorded environment; empty when it is clean."""
    pt_keep = (
        "PATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "USER",
        "LOGNAME",
        "SHELL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
    )
    problems = [f"{k} inherited" for k in env if k.startswith("PONYTAIL_")]
    problems += [
        f"{k} is not in the cell's allow list"
        for k in env
        if k not in pt_keep + FRESH and not k.startswith("PONYTAIL_")
    ]
    problems += [
        "CLAUDE_CODE_DISABLE_CLAUDE_MDS set: instruction files are off"
        for k in env
        if k == "CLAUDE_CODE_DISABLE_CLAUDE_MDS"
    ]
    for k in FRESH:
        if k not in env:
            problems.append(f"{k} not set to a fresh folder")
        elif not Path(env[k]).resolve().is_relative_to(cell.resolve()):
            problems.append(f"{k} outside the cell")
    return problems


def _files(root: Path) -> list[str]:
    return (
        sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        if root.exists()
        else []
    )


def check_cell(
    cell: Path, arm: str, task: dict, pinned: Path, no_run: str
) -> list[tuple[str, bool, str]]:
    """The isolation and install checks of one built cell: (check, passed, detail)."""
    ws, ev = cell / "ws", cell / "evidence"
    rec = json.loads((ev / "dry_run.json").read_text(encoding="utf-8"))
    cmd, env = rec["cmd"], rec["env"]
    built = Path(
        rec["cwd"]
    ).parent  # where the cell was built and claude would run; run.py moves it after
    out = []
    plugin_dirs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--plugin-dir"]
    want = [str(pinned.resolve())] if arm == "ponytail" else []
    out.append(("plugin dir", plugin_dirs == want, f"{plugin_dirs or 'none'}"))
    append = (
        cmd[cmd.index("--append-system-prompt") + 1] if "--append-system-prompt" in cmd else None
    )
    out.append(
        ("same NO_RUN text", append == no_run, "identical" if append == no_run else "differs")
    )
    out.append(
        (
            "stream-JSON output",
            "stream-json" in cmd and "--verbose" in cmd,
            "kept for the loading check",
        )
    )
    problems = check_env(env, built)
    out.append(
        (
            "environment",
            not problems,
            "; ".join(problems) or "allow list only, fresh folders, no PONYTAIL_*",
        )
    )
    fresh = {
        k: _files(cell / Path(env[k]).resolve().relative_to(built.resolve()))
        for k in ("HOME", "CLAUDE_CONFIG_DIR")
        if k in env and not problems
    }
    out.append(
        (
            "fresh home and config",
            not any(fresh.values()),
            f"{sum(map(len, fresh.values()))} file(s)",
        )
    )
    seeded = set(task.get("seed", {}))
    present = [f for f in PROJECT_FILES if (ws / f).exists() and f not in seeded]
    expected = {"AGENTS.md", ".claude/skills", ".outcomebound"} if arm == "ob" else set()
    out.append(
        ("project instruction/settings files", set(present) == expected, f"{present or 'none'}")
    )
    if arm == "ob":
        missing = [f for f in OB_FILES if not (ws / f).is_file()]
        harness = (
            "claude-code" in (ws / ".outcomebound/manifest.json").read_text(encoding="utf-8")
            if not missing
            else False
        )
        out.append(
            (
                "OB install (adopt --harness claude-code)",
                not missing and harness,
                f"missing {missing}" if missing else "present",
            )
        )
    installed = json.loads((ev / "installed.json").read_text(encoding="utf-8"))
    manifest = set(json.loads((ev / "_fixture_files.json").read_text(encoding="utf-8")))
    base = set(_git("ls-tree", "-r", "--name-only", "HEAD", cwd=ev / "base").stdout.split())
    listed = (
        set(installed) <= manifest and set(installed) <= base and (bool(installed) == (arm == "ob"))
    )
    out.append(
        ("manifest lists the OB install as seeded", listed, f"{len(installed)} installed file(s)")
    )
    outside = all(
        not Path(rec[k]).resolve().is_relative_to(Path(rec["cwd"]).resolve())
        for k in ("stdout", "stderr")
    )
    strays = [f for f in _files(ws) if Path(f).name.startswith(("_claude", "_fixture_files"))]
    out.append(
        (
            "raw output and baselines outside the workspace",
            outside and not strays and (ev / "base" / ".git").is_dir(),
            f"{Path(rec['stdout']).parent.name}/ beside ws/",
        )
    )
    out.append(
        (
            "git initialised before seeding",
            (ws / ".git").is_dir() and bool(_head(ws)),
            "ws/.git with the base commit",
        )
    )
    return out


def count_check(pt, cell: Path, task_id: str, arm: str) -> tuple[int, int]:
    """Lines Ponytail's counter reports before and after a synthetic agent adds SYNTHETIC_LINES
    code lines, on a copy of the built cell; returns (before, added as counted)."""
    with tempfile.TemporaryDirectory(prefix="ob-ponytail-count-") as tmp:
        copy = Path(tmp) / cell.name
        shutil.copytree(cell, copy, symlinks=True)
        ws = copy / "ws"
        before = pt.score_workspace(task_id, arm, "dry", ws)["total_loc"]
        where = "backend/app/" if pt.TASKS[task_id].get("fixture") else ""
        target = ws / where / "agent_added.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "".join(f"agent_line_{i} = {i}\n" for i in range(SYNTHETIC_LINES)), encoding="utf-8"
        )
        after = pt.score_workspace(task_id, arm, "dry", ws)["total_loc"]
    return before, after - before


def dry_run(
    worktree: Path,
    clone: Path,
    commit: str,
    cells: tuple[list[str], list[str]],
    template: Path | None = None,
    out: Path | None = None,
) -> dict:
    """Run Ponytail's own dry run for `cells` (the tasks, then the arms) and check each cell."""
    tasks, arms = cells
    _prepared(worktree, commit)
    clone = clone.resolve()
    if _head(clone) != commit or _git("status", "--porcelain", cwd=clone).stdout.strip():
        raise SystemExit(
            f"the clone {clone} is not clean at {commit}; "
            "the ponytail arm must load the pinned plugin"
        )
    pt = load_harness(worktree, template)
    missing = [t for t in tasks if t not in pt.TASKS or not _fixture_ok(pt, t)]
    if missing:
        raise SystemExit(f"dry-run: unknown task or missing fixture: {missing}")
    out = (out or Path(tempfile.mkdtemp(prefix="ob-ponytail-dry-"))).resolve()
    pt.RUNS_DIR = out
    argv = [
        "run.py",
        "--dry-run",
        "--task",
        ",".join(tasks),
        "--arms",
        ",".join(arms),
        "--models",
        "opus",
        "--runs",
        "1",
        "--pinned-plugin",
        f"ponytail={clone}",
        "--ob-launcher",
        str(LAUNCHER),
        "--ob-checks",
        str(CHECKS),
    ]
    saved = sys.argv
    sys.argv = argv
    try:
        pt.main()
    finally:
        sys.argv = saved
    run_dir = max(p for p in out.iterdir() if p.is_dir())
    report: dict[str, Any] = {
        "ponytail_commit": commit,
        "outcomebound": _head(REPO),
        "run_dir": str(run_dir),
        "cells": [],
        "counts": {},
    }
    failures = 0
    for cell in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        task_id, arm = cell.name.split("__")[:2]
        rec = json.loads((cell / "evidence" / "dry_run.json").read_text(encoding="utf-8"))
        print(f"\n=== {cell.name}\n$ {shlex.join(rec['cmd'])}  (cwd {rec['cwd']})")
        print("  env: " + " ".join(f"{k}={v}" for k, v in sorted(rec["env"].items())))
        checks = check_cell(cell, arm, pt.TASKS[task_id], clone, pt.NO_RUN)
        before, added = count_check(pt, cell, task_id, arm)
        checks.append(
            (
                "line counter",
                added == SYNTHETIC_LINES,
                f"{added} of {SYNTHETIC_LINES} synthetic lines counted; {before} before",
            )
        )
        report["counts"].setdefault(task_id, {})[arm] = before
        for name, ok, detail in checks:
            print(f"  {'ok ' if ok else 'XX '} {name}: {detail}")
            failures += 0 if ok else 1
        report["cells"].append(
            {
                "cell": cell.name,
                "checks": [{"check": n, "ok": ok, "detail": d} for n, ok, d in checks],
            }
        )
    for task_id, by_arm in report["counts"].items():
        same = len(set(by_arm.values())) == 1
        print(
            f"{'ok ' if same else 'XX '} {task_id}: "
            f"lines before the agent, equal in every arm: {by_arm}"
        )
        failures += 0 if same else 1
    report["failures"] = failures
    (run_dir / "ob-dry-run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"\ndry run: {'PASS' if not failures else str(failures) + ' check(s) FAILED'}; "
        f"report {run_dir / 'ob-dry-run.json'}"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--clone", type=Path, required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("selftest")
    s.add_argument("--worktree", type=Path, required=True)
    s.add_argument("--template", type=Path)
    d = sub.add_parser("dry-run")
    d.add_argument("--worktree", type=Path, required=True)
    d.add_argument("--clone", type=Path, required=True)
    d.add_argument("--commit", required=True)
    d.add_argument("--tasks", required=True)
    d.add_argument("--arms", default="baseline,ponytail,ob")
    d.add_argument("--template", type=Path)
    d.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.verb == "prepare":
        prepare(args.clone, args.commit, args.out)
        return 0
    if args.verb == "selftest":
        return 1 if selftest(args.worktree, args.template) else 0
    report = dry_run(
        args.worktree,
        args.clone,
        args.commit,
        ([t.strip() for t in args.tasks.split(",")], [a.strip() for a in args.arms.split(",")]),
        args.template,
        args.out,
    )
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
