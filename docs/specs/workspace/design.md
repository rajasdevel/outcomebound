---
name: workspace
status: ratified
---

# Workspace audit — design

## Outcome

An agent or a person who must tidy the worktrees of a project decides from facts. `outcomebound
workspace audit` reports each Git worktree and which of them pass the mechanical part of the
workspace guidance's removal rule. It never removes, prunes or changes anything.

The one invariant: the report is a read. Only `git` runs, with Git's optional locks off and no
lazy fetch, so that a partial clone cannot fetch objects during the read, and
`removable` means only "no changed path, no untracked path that Git does not ignore, and every
commit kept". Whether the task is finished, and whether an ignored file is still needed, cannot
be known by a tool. A person or an agent decides those. How: `outcomebound_tools/workspace.py`.
The worktree listing is the one `adopt_worktrees.parse` reads.

This is its own design, not a section of the install design, because the verb has its own
contract and does not install anything.

## Use

`outcomebound workspace audit [<target>] [--json]`. The target is any folder of the project
(default `.`).

For each worktree whose folder exists, the report has: path, branch, `main` (the first listed,
the main checkout, never removable), `state`, `changed` and `untracked` counts, last commit date
and age in days, and size in bytes. In `--json` each worktree object also has `removable` and `bytes_complete`
(false when a folder could not be read in full). Worktrees that Git lists but whose folder is gone are listed
as `prunable`. With `--json` the same data is one object: `version`, `default_branch`,
`worktrees`, `prunable`, `counts` by state, `removable` and `bytes`.

Exits: 0 a report; 1 Git failed or the target is outside a work tree; 2 a usage error, which
includes a target that is not a folder (`WORKSPACE_TARGET_NOT_FOLDER`).

The `workspace` fragment names the verb once, for resuming work and after a compaction. A person
also finds it through `outcomebound --help` and `README.md`.

## The facts

- **State of the commits**, from the HEAD commit of the worktree. `merged`: the default branch
  holds it. `pushed`: a remote-tracking branch holds it, and the default branch does not.
  `local`: only local refs or none hold it. `unknown`: Git could not say. The default branch is
  the one `refs/remotes/origin/HEAD` names, else a local `main` or `master`. A squash merge leaves
  the branch's own commits outside the default branch, so such a worktree reads `local` or
  `pushed` until its branch is deleted; the report does not guess.
- **Changed**: paths with any status in `git status`, other than untracked or ignored.
  **Untracked**: untracked paths Git does not ignore, file by file.
- **Size**: the bytes of regular files under the folder, found by walking it with the standard
  library. A symbolic link is skipped and not followed. If a folder cannot be read the size is
  marked partial.
- **Removable**: a linked worktree whose state is `merged` or `pushed` and with zero changed and
  zero untracked paths. The report states that ignored files are not looked at.

`outcomebound where` (see the [lifecycle design](../lifecycle/design.md)) reads `default_branch`,
`classify` and `changes` of `workspace.py` as a second reader. Its worktree lines must keep the
classification of this audit, so a change to the state rules here changes `where` too.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| Reachability is tested from the worktree's HEAD commit, not from its branch name | The branch name: a detached worktree or a renamed branch would then read wrong | agent | decided |
| Ignored files are not counted | Counting them: a walk over build folders makes the audit slow, and the fragment leaves their worth to the agent | agent | decided |
| The verb has no remove or prune option | A `--remove` flag: deletion stays an act of the agent that holds the task | agent | decided |
| `removable` states only what the tool can know: a linked worktree whose commits are merged or pushed and that has no changed or untracked path. Whether the task is finished and whether an ignored file is still needed are not known to the tool, and the report says so | A verdict that a worktree is finished, drawn from its age or its branch name, which would make an agent remove work that it cannot show is done | agent | decided |

## Validation

`tests/test_workspace.py` builds a clone with a pushed default branch and worktrees in each state
and checks the states, the counts, the removable rule, the prunable entry (and that the listing is
unchanged after the audit), the size walk with a symbolic link, the output, and the exit codes.
