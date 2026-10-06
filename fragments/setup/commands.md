---
id: commands
family: setup
applies: any repository where an agent runs commands
condition: when running a command whose output you read
detect: ["."]
version: 3
---
**Context** — a harness may give a command a terminal, and all it prints is context spent. A pager
waits for a key: `git --no-pager`, a tool's `--no-pager`, else `PAGER=cat`. An editor waits:
`git commit -m`, `--no-edit`, `GIT_EDITOR=true git rebase --continue`. A prompt must fail with its
reason: `GIT_TERMINAL_PROMPT=0` for git remotes, `ssh -o BatchMode=yes -o ConnectTimeout=10 -o
LogLevel=ERROR` (never `-q`), `sudo -n`. Stdin may never close: `< /dev/null` where no input is
meant (`codex exec`, `ssh` in a loop). Follow, watch and server commands never exit: bound them
(`tail -n`, `--tail`) or run them in the background; run a test runner in its single-run mode
(`vitest run`), not its watch mode. A command that ends but may outlast the harness's foreground
limit (a full suite, a build, a migration) runs in the background with its output and exit code
in a file; wait for it to exit, then read the file. Bound output at its source (`-n`, `--stat`,
`rg -m`). Send long output to a file, under a task folder such as `.agents/work/<task>/` where the
repository has one, else a temporary file, then read its exit code and its tail and search it for
the first error (`| tail` reports tail's exit code); `curl -fsS`, never `-s` alone.
**Bounds** — these commands are written for a POSIX shell; in PowerShell or cmd, use the shell's own
form of each. A probe the sandbox denies (a network call, a write outside the tree) is
`UNVERIFIED`, never absent or failed. A job that outlives the task (a scheduled run, a background
service) needs the person's grant, which names what it runs and how it stops. Quiet comes from a tool's own flags, never from hiding an error or disabling a check.
Slow is not hung: never shorten, skip or kill a check because it takes long; let it run to its end.
A command that was stopped can leave a lock or a half-done change: look before the next run.
**Mechanisms** — `runtime-check` when a claim is about what a command does: run it and read its
result, not its help text.
**Completion bar** — a command that was stopped or timed out is reported `UNVERIFIED`, never as
passed; a check's verdict comes from its own exit code and its error text.
**Distinguish** — quiet ≠ hidden; the exit code of a pipe ≠ the exit code of its command; stopped ≠
failed; slow ≠ hung.
