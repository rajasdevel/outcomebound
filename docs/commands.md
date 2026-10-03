# Command habits

An agent runs commands and reads their output. Two problems occur:

- A command can stop and wait for a person. A pager, an editor or a password prompt waits for a
  key that does not come. This occurs when the harness gives the command a terminal.
- A command can print too much. All the output goes into the agent's context. Long input makes
  the model less accurate, and the harness cuts long output.

The `commands` fragment tells the agent to use the habits below. They work in Claude Code, Codex,
Cursor, Gemini CLI and Amp. Where a harness already prevents a problem, the habit has no effect
and does no harm. No habit hides an error. No habit disables a security check.

Use the `commands` fragment in any repository where an agent runs commands.
`outcomebound adopt . --detect` proposes it for every repository. The habits help everywhere, and
the agent reads the fragment only when it runs a command.

## Habits that prevent a wait

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

## Habits that keep output small

- **Limit output at its source.** Use `git log -n 20 --oneline`, `git status -sb` and
  `git diff --stat` before `git diff`. Use `rg -m 20`, `rg -l` or `rg -c`. Before you read an
  unknown file, use `wc -c` and `head`. For minified files, use
  `rg --max-columns 200 --max-columns-preview`.
  - Fixes: large output in the context. In a test, `git diff` printed 10,005 lines and
    `git diff --stat` printed 2 lines. One minified line of 400 KB became 261 bytes.
  - Source: Anthropic, "Writing tools for agents"; test on 2026-10-03.
- **Send long output to a file.** Write the output to a file. Use a task folder such as `.agents/work/<task>/` when the repository has one. Else use a temporary file. Then
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

## Habits for a specified case

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

## Set it up

Add `commands` to the fragments of your install:

```sh
outcomebound adopt . --fragments commands,python
```

The list replaces the recorded list, so name every fragment that you want. `adopt` writes one
pointer line in `AGENTS.md` and the fragment in `.outcomebound/fragments/commands.md`. The agent
reads the fragment when it runs a command whose output it reads. `adopt . --remove` takes both
out.

## What it does not give you

The fragment is guidance that your agent reads. It does not stop a command, and an agent that
ignores it is not stopped. A habit that you write on the command line is the only protection in a
harness that gives a command a terminal. Report a command that was stopped or timed out as
`UNVERIFIED`. It is not a pass.
