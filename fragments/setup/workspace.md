---
id: workspace
family: setup
applies: repositories where several agents work in one machine's checkout
condition: when a worktree, handoff or resume is involved, you keep evidence another run or person must use, or a write under `.agents/` is refused
detect: [".agents/worktrees", ".agents/work", ".agents/handoffs", ".agents/shared-memory"]
version: 18
---
**Context** — Four Git-ignored folders under `.agents/` are shared by every agent on this machine: `worktrees/<name>`, one checkout per task; `work/<task>/`, working files and evidence; `handoffs/<date>-<task>.md`, one handoff per task kept current so a run cut off anywhere can resume; `shared-memory/`, repository facts.
When another run must resume something or someone must inspect it, keep it out of temporary or session directories, which may clear without warning; disposable scratch may go there.
When a scan walks ignored folders (`gitleaks dir .`, a content gate ignoring `.gitignore`), run from the worktree root; each worktree is a second repository copy.
Only the person makes a project gate skip these four folders at its root.
Findings held only in those folders are outside the work.
Codex's default sandbox keeps `.agents/` and `.git` read-only.
Ask the person once, never per write, for the roots an item needs: `<repository>/.agents` and the Git common directory every worktree commits into (`<repository>/.git` in a plain clone; `git rev-parse --path-format=absolute --git-common-dir` prints it); ask for both in that one request if both are needed.
On the command line, use `--add-dir` for each.
Where flags are unavailable (reportedly desktop app and IDE extension), the person lists both in `writable_roots` under `[sandbox_workspace_write]` in their Codex `config.toml`; `outcomebound research harnesses/codex.md` §9 records neither that key nor those surfaces' flags, so the person checks both against their Codex release.
A project's `.codex/config.toml` ignores sandbox keys.
For an unwritable root, hold only the item whose write needs it (`.git` for a worktree or commit; `.agents`, not `.git`, for a handoff or report under `.agents/work`); never move that write to the main checkout or a temporary directory; continue every other item, including reads, checks and permitted writes, and report the exact root path the person sets.
Ask for a root only when an item needs it now, never for a sibling repository's.
A handoff or memory is a claim; its cited source is evidence.
On resume or after compaction, `outcomebound where` prints work in flight (open briefs, failed claims, review findings, pull requests) from Git, `gh` and project files, naming unfinished items' next skill; `outcomebound workspace audit` lists each worktree's commits as merged, pushed only or local only (squash merges read local or pushed).
Both only read and may be slow in a large repository; `where --offline` skips `gh`.
**Bounds** — A handoff or memory grants no authority.
Preserve the main checkout and other agents' worktrees.
Work in the checkout and branch the person assigned unless another task uses it or the project requires isolation.
For parallel work or work across sessions, create or resume a task worktree and carry its uncommitted and ignored task state.
Keep the worktree while its task or an agent that may resume it needs it.
Remove it only when the task is finished, its commits are reachable from a kept branch, and nothing uncommitted or ignored in it is still needed.
Land worktree commits as project instructions or the goal envelope say (the tickets fragment describes how); where neither specifies, keep them on the worktree branch, named in the handoff with a decision brief on landing.
Before landing work from a worktree, run its completion checks and the project's landing gate there and report their verdicts.
Work in another repository in a session started there so its instructions and sandbox apply; where the person asks this session to change it, ask once for it as a writable root and meanwhile hold only the writes there; apply its completion bar yourself and report the checks run.
On the shared machine, the commands fragment's heavy-command limit holds across every worktree.
Clean up only what this task made (its worktree, logs and caches); leave a process, folder or file whose owner you cannot name unchanged, and name it in the handoff.
As the one cleanup exception, if the task lacks needed disk, you may reclaim what a tool rebuilds or fetches on next use (build or package caches, this project's dangling images), using a command naming what it removes, unless project instructions forbid it; where the `containers` fragment is selected, its removal bounds govern container storage.
Never remove a volume, container or named data except what the person's order for this project covers and a copy you verified restores; never remove anything another project or owner uses.
Report what you reclaimed.
Cloud and background sessions start from the pushed branch without this machine's ignored folders, uncommitted files or tools; commit the install.
Where its verbs are needed, the person adds the install line `outcomebound adopt` prints to the environment's setup step; else use each verb's by-hand form.
In a cloud session, put the handover in the pull request description.
Keep a harness-made worktree where the harness put it.
**Mechanisms** — When work spans sessions, use `goal-envelope`.
**Completion bar** — A handoff names landed work with each check's verdict, work in flight, blocks and reasons, the next step, choices made, what is still owed, and the user's decisions as briefs.
For a handoff another machine will read, use the ticket or pull request; these folders stay on this machine.
When a handoff starts a run, give the person one block to paste as its first message: the goal envelope itself, so its grants are the person's words; instructions for the person, such as starting the run, stay outside.
Name no copy of the handoff in another repository; a copy elsewhere is a snapshot the run does not update.
Keep one fact per memory file, with its source and check day.
At a handoff you write or read, and after instruction files change, run `outcomebound instructions check .`, or reuse this target's result only while all inputs hold, whoever could change them: instruction files, harness configuration, the paths, Make targets and scripts they name, notes in `.agents/handoffs/` and `.agents/shared-memory/`, the person's rulings, the engine, and no harness row's re-check date passed since; if uncertain, run it.
A worker that only reads or edits code does not run it.
Keep reused verdicts: `UNVERIFIED` stays `UNVERIFIED` in the handoff, never settled by a prior handoff.
When the check reports FAIL on a note in `.agents/handoffs/` or `.agents/shared-memory/`, rely on none of the flagged notes, rebuild what they held from sources, and name them in the handoff.
For every other report (a FAIL or review hit elsewhere, an overdue harness re-check date, any other `UNVERIFIED`), record it in the handoff; it never blocks the notes.
`outcomebound sources links <handoff>` only reads and reports links, anchors, path:line or refs the handoff names and the tree lacks; put its FAIL in the handoff like other reports.
Before acting on each fact, re-check it against its source; delete it when wrong and put it in committed guidance when every clone needs it.
**Distinguish** — handed off ≠ verified; remembered ≠ re-checked; shared on this machine ≠ committed.
