# Ponytail's benchmark with an OutcomeBound arm

[Ponytail](https://github.com/DietrichGebert/ponytail) is a lean-coding rule set for coding agents.
It ships its own agentic benchmark (`benchmarks/agentic/`): headless Claude Code sessions on 39
tasks, scored for size, cost and hidden checks. Ponytail is MIT-licensed. Its code is not copied into this
repository. It lives as a git clone in the evals home, a local folder outside this checkout
(`third-party/ponytail` in it), pinned to a commit, and its `LICENSE` with the MIT notice stays with
that clone. The patch here quotes some of
Ponytail's lines as context, and those lines stay under the same license. Task ids are Ponytail's.
This folder does not copy its prompts or task text.

| File | What it is |
| --- | --- |
| `driver.py` | Prepares a patched worktree of the pinned clone, runs the selftests, and runs the model-free dry run with its checks |
| `ob-arm.patch` | The adapter, against Ponytail's `run.py` and one line of `tasks.py` |
| `checks.py` | Our completion oracles for the repo-feature and open tasks, and the loading check. The patched `run.py` loads it with `--ob-checks` |

## What the patch changes

Each item names the place in Ponytail's `run.py` that it changes.

- `ARMS`: adds an `ob` arm. Its cell gets OutcomeBound's install (`outcomebound adopt . --harness claude-code`) and no extra prompt.
- New adapter block:
  - `--pinned-plugin ARM=PATH`, `--ob-launcher`, `--ob-checks` and `--dry-run`.
  - The fresh per-cell environment (`_cell_env`).
  - The evidence paths.
  - The cell build (`_build_cell`).
  - The stream-JSON reader.
- `_build_cell`: builds every arm's cell in this order: git init, seed (or copy the template), the ob arm's install, the manifest, the snapshot commit. The manifest, the list of installed files and a clone of the snapshot go to `cell/evidence/`. The agent works in `cell/ws/`.
- `code_stats`: reads the manifest from the evidence folder, and skips `.git`.
- `_git`: runs with no global or system git config. Scoring diffs against the evidence clone (`--git-dir`), never the agent's `.git`.
- `git_diff_stats`: diffs against the evidence clone.
- `score_workspace`:
  - Reads the stream-JSON result event from `cell/evidence/_claude.jsonl`. It falls back to upstream's `_claude.json`.
  - Applies our oracle where one exists, and keeps upstream's verdict as `correct_upstream`.
  - Records the loading check.
- `_base_cmd`: `--output-format stream-json --verbose`, so that the start event is kept.
- `warm_cache`: runs with a fresh cell environment, not the caller's.
- `run_cell`:
  - Builds the cell through `_build_cell`.
  - The plugin arms take only the pinned dir (`_pinned_plugin_dir`). There is no env override and no fallback to the user's plugin cache.
  - Raw output goes to `cell/evidence/`.
  - The environment is `_cell_env`: a new `HOME`, `XDG_*`, `CLAUDE_CONFIG_DIR` and `TMPDIR` under the cell. Only an allow list is inherited (PATH, locale, user, shell, and the three auth variables), so every `PONYTAIL_*` variable is left out.
  - Instruction files are not disabled for any arm.
  - `--dry-run` writes `cell/evidence/dry_run.json` (the command, the cwd, the environment with auth values shown as `<set>`, and the paths) and returns before `Popen`.
  - After a real call, `evidence_ok` compares the manifest digest and the base commit with their values before the call.
- `rescore`: reads the `cell/ws` layout.
- `main`:
  - Adds the new flags.
  - Refuses a plugin arm with no pinned dir, or the ob arm with no launcher, before any cell starts.
  - Builds cells as `cell/ws`.
  - Skips `warm_cache` and `claude --version` in a dry run.
- `tasks.py` `score_fixture`: reads the manifest from the evidence folder.

## Setup

The evals home is the folder that `OB_EVALS_HOME` names, else `outcomebound-evals` beside the main
checkout. It holds third-party clones and nothing of this repository. Clone Ponytail into it at the
pinned commit, and, for the repo-feature tasks, the FastAPI full-stack template at Ponytail's
pinned commit:

```sh
export OB_EVALS_HOME=/abs/path/to/outcomebound-evals
git clone https://github.com/DietrichGebert/ponytail "$OB_EVALS_HOME/third-party/ponytail"
git -C "$OB_EVALS_HOME/third-party/ponytail" checkout 09c434ab73ca43761c5d8b0c5d341926c2fba710
git clone https://github.com/fastapi/full-stack-fastapi-template "$OB_EVALS_HOME/third-party/full-stack-fastapi-template"
git -C "$OB_EVALS_HOME/third-party/full-stack-fastapi-template" checkout cd83fc1
```

## Commands

```sh
python3 evals/ponytail/driver.py prepare --clone <evals home>/third-party/ponytail \
    --commit 09c434ab73ca43761c5d8b0c5d341926c2fba710 --out <new folder>
python3 evals/ponytail/driver.py selftest --worktree <folder> [--template <template clone>]
python3 evals/ponytail/driver.py dry-run --worktree <folder> --clone <clone> --commit <sha> \
    --tasks safe-path,scope-rename,tmpl-be-count,vibe-csvstats --arms baseline,ponytail,ob \
    [--template <template clone>] [--out <folder>]
```

The repo-feature (`tmpl-*`) tasks need the FastAPI full-stack template (MIT, as its LICENSE says),
cloned at Ponytail's pinned commit `cd83fc1`. The driver passes its path to the harness process
only (`PONYTAIL_TMPL`). No cell inherits it. The tests find the clone through `OB_PONYTAIL_CLONE`,
else `OB_EVALS_HOME`, else `outcomebound-evals` beside the main checkout. Where the clone is absent,
the tests skip.

`prepare` runs `git apply --check` first. If the patch does not apply, it removes the worktree and
stops before anything runs. The dry run imports the patched harness into a process that refuses to
start any program named `claude`. A real run (`run.py` without `--dry-run`) spends model quota, and
this driver never starts one.

## Dry run, 2026-10-21

Inputs: Ponytail `09c434ab73ca43761c5d8b0c5d341926c2fba710` and the template at `cd83fc1`.
OutcomeBound was the development branch just before this folder was first committed.
No model, `claude` or API call ran.

- **`selftest`:** PASS.
  - Ponytail's own `--selftest`: "all instruments valid".
  - Each of the 21 oracles: its good reference passes and its bad reference fails, through the patched `score_workspace`. Upstream passes all 42 references (`correct_upstream=1`), the bad ones included.
- **`dry-run`:** PASS, 12 cells (4 tasks x 3 arms, `baseline,ponytail,ob`).
  - Tasks: `safe-path` (a surgical task with a seeded file), `scope-rename` (a surgical task scored by diff), `tmpl-be-count` (a repo feature), `vibe-csvstats` (an open request).
  - Each cell passed these checks:
    - The ponytail cell has exactly one `--plugin-dir`, the pinned clone. The other cells have none.
    - The `NO_RUN` text is the same in every arm, and stream-JSON output is on.
    - The environment holds only the allow list and fresh folders under the cell. There is no `PONYTAIL_*` variable and no `CLAUDE_CODE_DISABLE_CLAUDE_MDS`.
    - The fresh home and config folders hold no file after the build, adopt included.
    - The ob cell has `AGENTS.md`, `.claude/skills/` and `.outcomebound/` (adopt for `claude-code`). The other cells have no project instruction or settings file.
    - The manifest and the base commit list the 22 installed files as seeded.
    - Raw output paths, the manifest and the base clone are outside `ws/`.
    - `ws/.git` holds the base commit.
    - The line counter counts exactly the 7 lines a synthetic agent added, in every arm.
  - Lines counted before the agent, equal in every arm: `safe-path` 3 (the seeded stub, which upstream also counts), the others 0. OutcomeBound's installed files are not counted.

## What stays UNVERIFIED

- Whether the subscription login works from a separate `CLAUDE_CONFIG_DIR` and `HOME`. On macOS, the stored login may be found through the user's home. If it fails, the fallback is to pass the kernel through `--append-system-prompt`, labelled as such.
- What the model actually loads. The start event's fields (`plugins`, `skills`) are read by `loading_check`. Whether the event also names the instruction files and the hooks is not known until a real cell. Until then, the check reports instruction files as `UNVERIFIED`, and a missing field is never a pass.
- Whether Ponytail's start hook and band run correctly with the fresh `XDG_CONFIG_HOME` and `HOME`. The cell's home starts empty, so the defaults apply.
- Which Claude Code version a real run uses. The dry run does not call the CLI.

## Limits

- The evidence folder is beside the workspace, not access-protected. With `bypassPermissions`, an agent's write tools can reach any path. After the call, `evidence_ok` flags a changed manifest or base commit, but it does not cover the raw output.
- Every arm's cell is now a git repository with one base commit, the seed tasks included. Upstream made one only for diff-scored tasks. This is the same for every arm.
- The repo-feature oracles are static: they read routes and components and build nothing. The template's dependencies are not installed, and Bash is blocked for the agent.
- The open-task oracles run the produced script on a stated input, or drive the functions they find by name. Where they cannot decide (a module that is not installed, or an interactive app), the upstream verdict stands, and the reason starts with `undecided`.
- No planted constraint was added to any prompt. That would change Ponytail's tasks, so it is a separate decision.
- Ponytail's model judges (`answer.py`, `complete.py`, `judge.py`) still read the old layout (`_claude.json` in the workspace). They are not adapted.
