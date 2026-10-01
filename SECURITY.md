# Security policy

## Supported versions

Security fixes go into the latest release. To take one, install that release and run
`outcomebound adopt` again, as [Keeping it current](README.md#keeping-it-current) describes.

## Reporting a vulnerability

Report it privately through GitHub: on the repository's **Security** tab, choose **Report a
vulnerability** (<https://github.com/rajasdevel/outcomebound/security/advisories/new>). The
report, and the work on a fix, stay between you and the maintainers until an advisory is
published.

A report is easiest to act on when it gives:

- the version, from `cat "$(outcomebound home)/VERSION"`, and how OutcomeBound was installed:
  `uv tool install`, `pipx install`, `pip install` into a virtual environment, or a checkout;
- the operating system, the Python version and, where one is involved, the harness;
- the smallest reproduction you have: the commands, and a synthetic repository or files that
  trigger it;
- what an attacker gains, and what they need first, such as a merged pull request or write
  access to a file a harness loads;
- whether you have told anyone else.

## What not to post publicly

Do not open an issue, a pull request or a discussion about a vulnerability, and do not publish a
reproduction or an exploit before its advisory is out. Keep real credentials, private code and
personal data out of the private report too: a synthetic reproduction is enough.

## What OutcomeBound promises

A report that shows one of these broken is a vulnerability:

- `adopt` writes only inside its target, never through a symlink and never into `.git`;
- reading a target, whether for its project facts, for `adopt --detect` or for
  `outcomebound instructions check`, runs nothing the target holds;
- the launcher never runs an engine from the caller's directory or from `PYTHONPATH`;
- the finish check runs only the Done commands the manifest records, and none when their digest
  differs from the one in the hook entry;
- the engine opens no network connection; `floor provision --accept` runs pip, which does.

Some behavior is by design. The Done commands and the floor's tools run with your privileges, as
your own commands would. A pull request can change the recorded Done commands and the hook entry
together, so the hook is one more committed file a review must read, and
`outcomebound instructions check` reports it on every run
([finish-check design](docs/specs/finish-check/design.md#edges)). A clean
`instructions check` does not rule out an injection: it claims only the classes of content it
lists.
