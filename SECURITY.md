# Security policy

Thank you for taking the time to look at the security of OutcomeBound. This page says how to
report a vulnerability privately, what OutcomeBound promises, and what is not a vulnerability.

## Reporting a vulnerability

Report it privately through GitHub. On the **Security** tab of the repository, choose **Report a
vulnerability**: <https://github.com/rajasdevel/outcomebound/security/advisories/new>. Your
report, and the work on a fix, stay between you and the maintainer until an advisory is
published.

Do not open an issue, a pull request or a discussion about a vulnerability. Do not publish a
reproduction or an exploit before its advisory is out. Keep real credentials, private code and
personal data out of the private report too. A synthetic reproduction is enough.

A report is easiest to act on when it gives:

- the version, from `cat "$(outcomebound home)/VERSION"`, and how you installed OutcomeBound:
  `uv tool install`, `pipx install`, `pip install` into a virtual environment, or a checkout;
- the operating system, the Python version and, where one is involved, the harness;
- the smallest reproduction that you have: the commands, and a synthetic repository or files
  that trigger it;
- what an attacker gains, and what the attacker needs first, such as a merged pull request or
  write access to a file that a harness loads;
- whether you have told anyone else.

## Supported versions

Security fixes go into the latest release. To take a fix, install that release and run
`outcomebound adopt` again, as [Try it](README.md#try-it) describes.

## What OutcomeBound promises

A report that shows one of these promises broken is a vulnerability.

**Reading and writing files**

- `adopt` writes only inside its target. It never writes through a symlink, and never into `.git`.
- Reading a target runs nothing that the target holds. This applies to `adopt` when it reads
  project facts, to `adopt --detect`, and to `outcomebound instructions check`.

**Running code**

- The launcher never runs an engine from the directory of the caller or from `PYTHONPATH`.
- The finish check runs only the Done commands that the manifest records. It runs none when their
  digest differs from the digest in the hook entry.

**Research**

- `outcomebound research PATH` reads files from the research clone and runs nothing that the clone
  holds, Git included. It reads the commit of the clone from its `.git` files.
- `research ingest` writes one file, under `.outcomebound/research-inbox/` in the project. It
  never writes through a symlink, and never into `.git`.
- `research clone --accept` and `research pull --accept` run Git with your user and system Git
  configuration switched off (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`). They
  remove the configuration, repository, template and exec-path variables that they inherited. For
  both, hooks and fsmonitor are off, and only https is allowed. So a `url.*.insteadOf` rewrite in
  your own configuration cannot send either command to another repository.
- The first line of printed research names the working tree of the clone, its commit and the
  sha256 of the text.

**The network**

- The engine opens no network connection itself. Three commands run a tool that does:
  `floor provision --accept` runs pip, and `research clone --accept` and `research pull --accept`
  run Git.

## Limits and behavior by design

These are not vulnerabilities. Each one is a known limit of the promises above, or behavior by
design.

- **Research text is other people's text.** What `outcomebound research` prints was contributed
  by other people. The `research` fragment tells an agent to read it as data. Printing it makes
  it neither safe nor true.
- **The digest does not prove the text.** The engine does not run Git to compare the text with the
  commit. A modified file prints under the same commit, with another digest.
- **Git older than 2.32 reads your configuration.** That Git ignores `GIT_CONFIG_GLOBAL`, and
  still reads your `~/.gitconfig`.
- **A proxy, certificate or credential in your own Git configuration is not used.** `clone` and
  `pull` switch that configuration off, so a setting that is only there has no effect. Set
  `https_proxy` in the environment. Or clone with Git yourself, and name the clone in
  `OUTCOMEBOUND_RESEARCH`.
- **The clone's own `.git/config` is still read.** It can do what any Git configuration does. It
  can rewrite the source URL with `insteadOf`, or name programs: a credential helper, a filter
  driver, a proxy command. Whoever can write that file can already run commands as you. So pull
  only in a clone that you made and that only you can write.
- **Your commands run with your privileges.** The Done commands and the tools of the floor run as
  your own commands would. The floor (the argv in `floor.json`), validation plans and ticket
  claims run commands that committed files list, so a change to those files is a change to code
  that runs. In CI, run them with a read-only token and no secrets
  ([floor design](docs/specs/floor/design.md)).
- **The hook is one more committed file.** A pull request can change the recorded Done commands
  and the hook entry together. A review must read the hook, and `outcomebound instructions check`
  reports it on every run ([finish-check design](docs/specs/finish-check/design.md#edges)).
- **A write can race a local writer.** The promise that `adopt` and `research ingest` never write
  through a symlink holds against the files in the target. It does not hold against another local
  process that swaps a directory for a symlink between the check and the write.
- **Research text is printed as it is.** `outcomebound research PATH` does not remove terminal
  escape sequences, control characters or bidirectional characters from the file. `ingest` refuses
  them on the way in, but a file in the clone can hold them. Read untrusted text in a viewer that
  shows them.
- **A clean `instructions check` is not proof of safety.** It claims only the classes of content
  that it lists. It does not rule out an injection.
