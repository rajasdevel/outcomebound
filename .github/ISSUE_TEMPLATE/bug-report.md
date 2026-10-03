---
name: Bug report
about: Something in the engine, a skill or a template did not do what the documents say
title: ""
labels: bug
---

Thank you for the report. A small, exact example helps most. Use synthetic names and data, and
keep credentials, private code and personal data out of this issue. If the problem is a security
vulnerability, do not post it here. Report it privately, as `SECURITY.md` describes:
<https://github.com/rajasdevel/outcomebound/security/advisories/new>.

## Observed

What happened. Paste the exact output if you can.

## Expected

What should have happened, and where it says so: `OutcomeBound.md`, the block in your
`AGENTS.md`, the `README.md`, a skill, or `docs/specs/<area>/design.md`.

## Commands, output and exit codes

```
$ <the exact command>
<its output>
<its exit code, from: echo $?>
```

## Environment

- OutcomeBound version (`cat "$(outcomebound home)/VERSION"`, or the tag or commit of your checkout):
- How you installed it (`uv tool install`, `pipx install`, `pip install` or a checkout):
- Python version (`python3 --version`):
- Harness (Claude Code, Codex, Cursor, Gemini CLI, Amp or `--harness generic`), if one is involved:
- Operating system:

## Additional context

Anything else that narrows the cause: the smallest reproduction that you found, the related files,
or a link to a run.
