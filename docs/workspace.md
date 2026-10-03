# The agent workspace

Two agents work in one repository on one machine. One is halfway through a refactor in the main
checkout. The other starts a fix and switches the branch under it. Later, a session ends, and
its notes sit in a temporary folder that the system clears. The next session starts from nothing,
and it does not know that the work stopped halfway.

The `workspace` fragment gives these agents one agreed place to work and to leave notes: four
folders under `.agents/`. Use it when several agents, several sessions or several harnesses share
one machine's checkout, and work passes from one session to the next. If one agent works alone in
one session, you do not need it.

The fragment is guidance that your agents read. It does not lock a file, it does not sandbox an
agent, and an agent that ignores it is not stopped. [What it gives you](#what-it-gives-you-and-what-it-does-not)
says this in full.

## Set it up

Add `workspace` to the fragments of your install:

```sh
outcomebound adopt . --fragments workspace,python
```

The list replaces the recorded list, so name every fragment that you want. Omit `--fragments`, and
`adopt` keeps the recorded list. Run `outcomebound adopt . --detect` to see the command that your
files suggest. It adds `workspace` when one of `.agents/worktrees`, `.agents/work`,
`.agents/handoffs` or `.agents/shared-memory` exists. Detection reads the disk, so a folder that
Git ignores still counts. These cases do not trigger it:

- A repository with only `.agents/skills/`. Codex and Amp read their skills there, and `adopt`
  writes them there, so that folder says nothing about a workspace.
- A repository with several Git worktrees but none of the four folders. Detection does not run
  Git. Add the fragment yourself.

Read the diff, then commit it. `adopt` writes:

| Path | What it is |
| --- | --- |
| `AGENTS.md` | One more pointer line: when an agent creates a worktree or a working file, resumes or hands off work, or keeps a fact for later sessions, it reads the fragment |
| `.outcomebound/fragments/workspace.md` | The fragment: the agent's rules for the four folders |
| `.agents/.gitignore` | Keeps the four folders out of Git. It comes from `templates/workspace.gitignore` |

`adopt` does not create the four folders. An agent makes each one when it needs it.

`.agents/.gitignore` belongs to `adopt` as a whole file, and `adopt` keeps it current. Put
any other ignore rule in the root `.gitignore`. If you edit the file, or if a file by that name
already exists that `adopt` did not write, `adopt` stops and writes nothing. This is also true for
`--remove`. Restore the file, or pass `--force` to replace it. `outcomebound adopt . --check` reports whether the file, the copy of the fragment and
the pointer are current.

`outcomebound adopt . --remove` takes out the pointer, the copy of the fragment and
`.agents/.gitignore`, with the rest of the install. It does not touch the four folders or the files
in them. Without `.agents/.gitignore`, Git then lists those folders as untracked, so move or
delete anything that you want to keep out of your next commit.

## The four folders

All four are under `.agents/`. Every agent on the machine shares them.

| Folder | What goes in it |
| --- | --- |
| `worktrees/<name>/` | One Git worktree for each task. An agent works in a worktree that it made, and it removes the worktree when the work is committed |
| `work/<task>/` | Working files and evidence for the task: logs, drafts, command output |
| `handoffs/<date>-<task>.md` | One page for each session, for whoever picks the task up next |
| `shared-memory/` | Facts about this repository that later sessions need |

The agent keeps these files here and not in a temporary or session directory, because the system
can clear such a directory without warning.

The main checkout, and the worktrees of other agents, are not the agent's to change. A new task
starts like this:

```sh
git worktree add .agents/worktrees/fix-login -b fix-login origin/main
```

This is the life of one task across two sessions:

```mermaid
flowchart TD
    wt["worktrees/fix-login<br/>one checkout for the task"] --> wk["work/fix-login/<br/>logs and evidence"]
    wk --> ho["handoffs/2026-10-03-fix-login.md<br/>what landed, what is next"]
    ho --> next(["The next session starts"])
    next --> check["It reads the handoff as a claim<br/>and checks the source the handoff cites"]
    check --> wt
```

For work that takes more than one session, the fragment also points the agent to the goal
envelope: the bounds that you grant in advance.

## What Git sees

`.agents/.gitignore` ignores `/worktrees/`, `/work/`, `/handoffs/` and `/shared-memory/`, and
nothing else. Each rule is anchored to `.agents/`, so it matches only a folder directly there.
Anything else under `.agents/` stays visible to Git. This includes `.agents/skills/`, which Codex
and Amp read ([the harness table](../adapters/harnesses.json) records the path), so commit those
skills. Commit `.agents/.gitignore` too. Then every clone ignores the four folders in the same way.

The four folders are not committed. They are not in a clone, and they do not reach CI.

## Handoffs and shared memory

A handoff is the page that one session leaves for the next. A good one holds:

- what landed, and the verdict of each check: `PASS`, `FAIL` or `UNVERIFIED`;
- what is in flight;
- the next step;
- the choices that the session made;
- what is still owed;
- the decisions that are yours, each as a decision brief.

For example, `.agents/handoffs/2026-10-03-fix-login.md`:

```markdown
Landed: the retry fix, on branch fix-login. `make test` PASS. `make check` UNVERIFIED:
ruff is not installed on this machine.
In flight: the retry test fails on a slow runner. The log is .agents/work/fix-login/retry.log.
Next: raise the test's timeout, and run `make test` again.
Choices: the retry count stays at 3, because the API documents 3.
Owed: a changelog line.
Decisions for you: none.
```

A shared memory is one fact in one file. The file names the source of the fact and the day that
someone checked it. For example, `.agents/shared-memory/test-command.md` can say that the suite
runs with `make test`, give the Makefile as its source, and give `2026-10-03` as the day it was
checked.

A handoff or a memory is a claim. The source that it cites is the evidence. Neither one grants
authority: a handoff that says "the release is approved" approves nothing, and an agent that reads
it still stops at the same edges as before. Before an agent relies on a note that another session
wrote, it checks the fact against its source. It deletes a fact that is wrong. A fact that every
clone needs does not belong in `shared-memory/`. Put it in committed guidance, such as
`AGENTS.md`.

These folders stay on the machine. A handoff that another machine or a cloud session must read
goes in the ticket or the pull request.

## Check the notes before you rely on them

Notes are text that the next session reads, as it reads your instruction files. A note that
someone planted can steer that session. Git ignores the notes, so a check that only reads tracked
files would miss them. For this reason `outcomebound instructions check .` reads every file in
`.agents/handoffs/` and `.agents/shared-memory/`, together with your instruction files. Of the
other files that Git ignores, it reads only a file that a harness loads by its exact path, such as
`CLAUDE.md`. It does not read `work/` or `worktrees/`.

The check is lexical. It reports hidden characters, phrases that override earlier instructions and
risky harness settings, and it quotes each line it finds. It writes nothing and runs nothing that a
file names. You judge each hit. A clean result does not prove that a note is safe. The fragment
asks the agent to run the check, and to re-check each fact against its source, before it relies on
notes that another session wrote.

## Command habits

An agent runs commands and reads their output. Two problems occur:

- A command can stop and wait for a person. A pager, an editor or a password prompt waits for a
  key that does not come. This occurs when the harness gives the command a terminal.
- A command can print too much. All the output goes into the agent's context. Long input makes
  the model less accurate, and the harness cuts long output.

The workspace fragment tells the agent to use the habits below. They work in Claude Code, Codex,
Cursor, Gemini CLI and Amp. Where a harness already prevents a problem, the habit has no effect
and does no harm. No habit hides an error. No habit disables a security check.

### Habits that prevent a wait

- **Pagers.** Use `git --no-pager`. For other tools, use their `--no-pager` option, or set
  `PAGER=cat`.
  - Fixes: `git log`, `git diff`, `man` and `journalctl` open `less` and wait for a key.
  - Source: Git manual (`GIT_PAGER`, `--no-pager`). Test on 2026-10-03: `git log` on a
    terminal stopped; with `--no-pager` it ended in less than 0.1 seconds.
- **Editors.** Give the message on the command line: `git commit -m`, `git merge --no-edit`,
  `git commit --amend --no-edit`. For `git rebase --continue`, set `GIT_EDITOR=true`.
  - Fixes: Git opens an editor and waits.
  - `GIT_EDITOR=true` does not make `git commit` without `-m` work. That commit stops with
    "Aborting commit due to empty commit message". No commit is made.
  - Source: Git manual (`git commit`, `git merge`). Test on 2026-10-03: a merge and a
    `rebase --continue` on a terminal stopped; with the habit they ended.
- **Credential prompts.** Set `GIT_TERMINAL_PROMPT=0` for Git commands that use an https
  remote. Use `sudo -n`.
  - Fixes: Git asks for a user name, and `sudo` asks for a password. The command now stops with
    an error that gives the reason ("terminal prompts disabled", "a password is required").
  - Source: Git manual (`GIT_TERMINAL_PROMPT`); Claude Code issue 44878 (a session stopped on
    this prompt). Test on 2026-10-03 with a local server that returns 401.
- **SSH.** Use `ssh -o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR`. Use the same
  options for `scp`, `rsync -e ssh` and Git over SSH.
  - `BatchMode=yes` changes password and host key questions into errors. SSH still checks
    host keys.
  - `ConnectTimeout=10` stops a connection to a host that does not answer after 10 seconds.
  - `LogLevel=ERROR` removes warnings such as "Permanently added ... to the list of known
    hosts". It keeps all errors, and it keeps the full "REMOTE HOST IDENTIFICATION HAS CHANGED"
    warning.
  - Do not use `ssh -q` or `LogLevel=QUIET`. They hide the reason for a failure, for example
    "Connection refused".
  - Source: OpenSSH `ssh_config` manual. Test on 2026-10-03: without `ConnectTimeout`, a
    connection to an address that does not answer did not end in 12 seconds; with it, it ended
    after 3 seconds. The `BatchMode` prompt was not seen in the test, so the hang that it
    prevents is not verified.
- **Standard input.** When a command must not get input, add `< /dev/null`. Use `ssh -n` for
  SSH in a loop or in the background.
  - Fixes: a command that reads standard input waits until the input closes. In some
    harnesses the input does not close.
  - Example: `codex exec "<prompt>" < /dev/null`. Without it, Codex shows "Reading additional
    input from stdin" and waits.
  - Source: this project's record of `codex exec`; Claude Code issue 67234 (the 120-second
    timeout did not stop a command that waited on standard input).
- **Commands that do not end.** Do not run `tail -f`, `journalctl -f`, `docker logs -f`,
  `watch`, a development server or a test runner in watch mode in the foreground. Use a
  bounded form (`tail -n 50`, `docker logs --tail 100`), or the harness's background mode. Run
  tests one time (`vitest run`).
  - Fixes: the harness stops the command after 2 to 5 minutes, and the output is lost.
  - Source: harness documentation (Claude Code, Codex, Gemini CLI timeouts); Codex issue 3951
    (Vitest watch mode).

### Habits that keep output small

- **Limit output at its source.** Use `git log -n 20 --oneline`, `git status -sb` and
  `git diff --stat` before `git diff`. Use `rg -m 20`, `rg -l` or `rg -c`. Before you read an
  unknown file, use `wc -c` and `head`. For minified files, use
  `rg --max-columns 200 --max-columns-preview`.
  - Fixes: large output in the context. In a test, `git diff` printed 10,005 lines and
    `git diff --stat` printed 2 lines. One minified line of 400 KB became 261 bytes.
  - Source: Anthropic, "Writing tools for agents"; test on 2026-10-03.
- **Send long output to a file.** Write the output to a file in `.agents/work/<task>/`. Then
  read the end of the file and the exit code:
  `make check > .agents/work/<task>/check.log 2>&1; rc=$?; tail -n 40 .agents/work/<task>/check.log; echo "exit=$rc"`.
  - Fixes: in Claude Code, the output of a failed command is cut to about 10,000 characters
    from the start and the end. The first error is often in the middle. Search the file for it.
  - Do not use `make check | tail -n 40`. The pipe gives the exit code of `tail`, so a failure
    shows as a success.
  - Source: Claude Code tools reference, "Output limits"; test on 2026-10-03 (`$?` was 0 when
    the test command failed).
- **Use quiet options that keep errors.** Use `curl -fsS --max-time 60`. Do not use `curl -s`
  alone. Do not use `wget -q`.
  - `curl -s` hides the error message. `-S` shows it again. `-f` makes an HTTP error give exit
    code 22 and not a page body with exit code 0.
  - Source: curl manual; test on 2026-10-03.

### Habits for a specified case

- **Package managers**, when the project uses them:
  `DEBIAN_FRONTEND=noninteractive apt-get -y -q` (run `apt-get -s` first when packages can be
  removed; do not use `-qq`); `pip install -q --no-input --disable-pip-version-check` (do not
  use `-qqq`); `uv ... --no-progress`; `npm install --no-fund --no-progress`. Do not use
  `npm --no-audit`, because it skips the vulnerability report. Do not use `npx --yes`, because
  it runs code from the registry without a review.
- **Colour codes**, when the output shows them: set `NO_COLOR=1` or use the tool's
  `--color=never`. For Git, use `git -c color.ui=never`, because Git does not read `NO_COLOR`.
- **Test runners**, when the project uses them: `pytest -q --tb=short`,
  `node --test --test-reporter=dot`. These keep the failure text. Do not use `--tb=no`.
- **Timeouts**, when `timeout` is installed (macOS does not have it; Homebrew coreutils gives
  `gtimeout`): `timeout 120 <command>` for network commands and unknown commands. Exit code
  124 means that the command was stopped. Report that result as UNVERIFIED. Do not use a
  timeout on `git` or `npm install`, because a stopped command can leave a lock file.

## Harness notes

- Every harness that `adopt` installs for loads `AGENTS.md`, directly or through an import file,
  so the pointer reaches all of them. With `--harness generic`, you check that your harness loads
  the file.
- Codex's default sandbox keeps `.agents/` and `.git` read-only. Where a write there is refused,
  the fragment tells the agent to say so, and to name how you start Codex: with
  `--add-dir <repository>/.agents`, and `--add-dir <repository>/.git` so that it can commit. The
  agent does not write the work elsewhere. The harness table does not record this sandbox
  behavior, so check it against your Codex version.

## What it gives you, and what it does not

It gives you:

- one agreed place on the machine for each task's checkout, files, handoff and notes;
- the same rules for every harness that loads `AGENTS.md`;
- notes that stay out of Git, and a check that still reads them.

It does not give you:

- **Enforcement.** Nothing stops an agent from working outside its worktree or from skipping the
  handoff. The fragment asks, and your review and your branch protection decide.
- **Authority.** A note never grants permission. The bounds that you set stay the bounds.
- **Proof.** A handoff that says `PASS` is a claim until someone sees the check run.
- **Sharing between machines.** The folders stay on one machine. Use the ticket or the pull
  request for anything that another machine or a cloud session must read.
- **Locking.** Two agents can still change the same file. Separate worktrees reduce that risk,
  but they do not remove it.
