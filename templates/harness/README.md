# Harness ask rules

These files are examples for you to copy. `adopt` never installs them, and the project owns
every rule in its copy. Each one makes the harness ask a person before a command that matches a
declared irreversible edge. The harness does the asking, so the engine adds no second filter.

| File | Harness | Copy it to |
| --- | --- | --- |
| `claude-code.settings.json` | Claude Code | `.claude/settings.json`; merge the `ask` list into any `permissions` object that is there |
| `codex.rules` | Codex | `.codex/rules/<name>.rules`; loads only where the project's `.codex/` layer is trusted |

For any other harness no template exists, because no primary source for its syntax has been
checked here: `UNVERIFIED`.

## Make them yours

The commands in the examples are placeholders for the edges that a project may declare: a push,
a tag, a publish, a release, an apply to a shared environment. Replace them with the commands
that cross the edges in your project's `edges:` line, and delete the rest.

## What a rule covers

A rule matches the command text that the model writes. It does not see what a script, a
Makefile target, an alias or a program that runs its arguments (`make`, `npx`, `docker exec`)
runs, and it does not match the same program called in
another form (a full path, `sh -c '...'`, an option put before the subcommand). A rule is a
prompt before the usual form of an act. It is not a permission system, a sandbox or a gate.
Guard an edge that must hold with the project's own gate, such as a protected branch, a
protected environment or a credential that the agent's account lacks.

Codex's page describes its rules as for commands that run outside the sandbox; whether a rule
fires for a command the sandbox already allows is `UNVERIFIED`.

A rule asks; it never allows. Do not add `allow` rules here, since they would loosen what the
harness already decides.

## Sources

Syntax checked on 2026-10-06; check it again when a harness changes:

- Claude Code: https://code.claude.com/docs/en/permissions (`permissions.ask`, `deny` and
  `allow` in `.claude/settings.json`; deny, then ask, then allow; `Bash(<prefix> *)`).
- Codex: https://learn.chatgpt.com/docs/agent-configuration/rules, which
  https://developers.openai.com/codex/exec-policy redirects to (`prefix_rule` with `pattern`,
  `decision` and `justification`; project rules under `.codex/rules/` in a trusted project).
