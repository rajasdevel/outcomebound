---
id: commands
family: setup
applies: any repository where an agent runs commands
condition: when running a command whose output you read
detect: ["."]
version: 1
---
**Context** — a harness may give a command a terminal, and all it prints is context spent. A pager
waits for a key: `git --no-pager`, a tool's `--no-pager`, else `PAGER=cat`. An editor waits:
`git commit -m`, `--no-edit`, `GIT_EDITOR=true git rebase --continue`. A prompt must fail with its
reason: `GIT_TERMINAL_PROMPT=0` for git remotes, `ssh -o BatchMode=yes -o ConnectTimeout=10 -o
LogLevel=ERROR` (never `-q`), `sudo -n`. Stdin may never close: `< /dev/null` where no input is
meant (`codex exec`, `ssh` in a loop). Follow, watch and server commands never exit: bound them or
run them in the background; tests run once. Bound output at its source (`-n`, `--stat`, `rg -m`).
Send long output to a file, under a task folder such as `.agents/work/<task>/` where the
repository has one, else a temporary file, then read its tail and its exit code (`| tail` reports
tail's); `curl -fsS`, never `-s` alone.
**Bounds** — quiet comes from a tool's own flags, never from hiding an error or disabling a check.
A command that was stopped can leave a lock or a half-done change: look before the next run.
**Mechanisms** — `runtime-check` when a claim is about what a command does: run it and read its
result, not its help text.
**Completion bar** — a command that was stopped or timed out is reported `UNVERIFIED`, never as
passed; a check's verdict comes from its own exit code and its error text.
**Distinguish** — quiet ≠ hidden; the exit code of a pipe ≠ the exit code of its command; stopped ≠
failed.
