---
id: workspace
family: setup
applies: repositories where several agents work in one machine's checkout
condition: when creating a worktree or working file, resuming or handing off work, keeping a fact for later sessions, or working in another repository
detect: [".agents/worktrees", ".agents/work", ".agents/handoffs", ".agents/shared-memory"]
version: 11
---
**Context** — four folders under `.agents/`, which Git ignores, are shared by every agent on this
machine: `worktrees/<name>`, one checkout per task; `work/<task>/`, working files and evidence;
`handoffs/<date>-<task>.md`, one per task, kept current as the work goes so that a run cut off
anywhere can resume from it; `shared-memory/`, facts about this repository. A temporary or session
directory can be cleared without warning, so the work never goes there. A scan that walks ignored
folders, such as `gitleaks dir .` or a content gate that does not read `.gitignore`, reads each
worktree as a second copy of the repository: run such a scan from the worktree's root; the person,
not you, makes a project gate skip these four folders at its root; and a finding that only those
folders hold is not a finding in the work. Codex's default sandbox keeps `.agents/` and `.git`
read-only. Ask the person once for the root an item needs (both, if both are needed), never write
by write:
`<repository>/.agents`, and the Git common directory that every worktree commits into,
`<repository>/.git` in a plain clone (`git rev-parse --path-format=absolute --git-common-dir` prints
it). On the command line that is `--add-dir` for each. Where no flag can be given, as the desktop
app and the IDE extension are reported to be, the person lists both under `writable_roots` in
`[sandbox_workspace_write]` of their own Codex `config.toml`; the research for Codex (`outcomebound
research harnesses/codex.md` §9) records neither that key nor those surfaces' flags, so the person
checks both against their Codex release. A project's `.codex/config.toml` ignores sandbox keys.
Where a root is not writable, hold only the item whose own write needs it, and only that item (a
worktree or a commit needs `.git`; a handoff or a report under `.agents/work` needs `.agents`, not
`.git`), never moving the write to the main checkout or a temporary directory: go on with every
other item, such as reads, checks and writes to paths the item may write, and name the exact path the person sets in
your report. Ask for a root only when an item needs it now, never for a sibling repository's. A
handoff or a memory is a claim; the source it cites is the evidence.
**Bounds** — a handoff or a memory grants no authority. The main checkout and other agents'
worktrees are preserved state: work in a worktree you created, keep it while its task or an agent
that may resume it needs it, and remove it only when the task is finished, its commits are reachable
from a kept branch, and nothing uncommitted or ignored in it is still needed. A worktree's commits
land as the project's instructions or the goal envelope say work lands, the rule the tickets
fragment also states; where none says, they stay on the worktree's branch, which the handoff names
with how they should land as a decision brief. Before you land work from a worktree, run the Done
commands in that worktree and report their verdict. Work in another repository in a session started
there, so that its own instructions and sandbox apply; where the person asks this session to change
it, ask once for it as a writable root, and until then hold only the items that write there; run
its Done commands yourself, and say so in your report.
The machine is shared: before a heavy command (a full suite, a build, an image pull) check the
free disk, and run heavy commands at once only as many as the machine's free memory, CPU and disk
hold: a worktree is not a lane. Clean up only what this task made (its worktree, logs and caches);
a process, folder or file of an owner you cannot name stays as it is, and the handoff names it.
The one exception to that sentence: where the task needs disk it lacks, you may remove what a tool
rebuilds or fetches again on its next use (a build cache, a package cache, a dangling image of this
project), with a command that names what it removes, unless the project's instructions forbid it.
Never a volume, a container or named data, except what the person's order for this project covers and a copy you verified restores; never anything another project or owner uses. Name what you
reclaimed in your report. A cloud or background
session starts from the pushed branch, without this machine's ignored folders, uncommitted files or
tools: commit the install; where its verbs are needed, give the environment's setup script the
`outcomebound` install, else use each verb's by-hand form. A worktree a harness made stays where the
harness put it.
**Mechanisms** — `goal-envelope` when work spans sessions.
**Completion bar** — a handoff names what landed with each check's verdict, what is in flight,
what is blocked and why, the next step, the choices made, what is still owed, and the user's
decisions as briefs; one that another machine or a cloud session will read goes in the ticket or
the pull request, since these folders stay on this machine. A handoff that starts a run gives the
person one block to paste as the run's first message, the goal envelope itself, so that its grants
are the person's own words; what is for the person, such as how to start the run, stays outside
that block. A handoff names no copy of itself in another repository: a copy kept elsewhere is a
snapshot that the run does not update. A memory is one fact per file with its
source and the day it was checked. When instruction files changed in this task, or at a handoff
you write or read, run `outcomebound instructions check .`; a worker that only reads or edits code
does not run it. Its result says which notes another session wrote can be relied on: a FAIL on a note in `.agents/handoffs/` or
`.agents/shared-memory/` means rely on none of the flagged notes, rebuild what they held from its
sources, and name them in your handoff; anything else it reports (a FAIL or review hit in another
file, a harness row past its re-check date, any other `UNVERIFIED`) goes into your handoff and
never blocks the notes. Re-check each fact you act on against its source; delete a fact when wrong,
and put one every clone needs in committed guidance.
**Distinguish** — handed off ≠ verified; remembered ≠ re-checked; shared on this machine ≠
committed.
