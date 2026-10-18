# Cloud sessions

A cloud session is an agent run on a machine that the harness's maker hosts. Examples are Claude
Code on the web, Codex cloud, GitHub Copilot's cloud agent and Cursor's cloud agents. The page for
Claude Code on the web says a session starts from a fresh clone
([page](https://code.claude.com/docs/en/claude-code-on-the-web)). The pages for the other three
describe an ephemeral or separate environment built from your repository, and this guide treats
them the same way; that is an inference. Facts here come from the makers' pages, read on
2026-10-17, and each is marked with its page. A fact that no page shows is marked `UNVERIFIED`.
No cloud session was run to write this guide.

## What arrives

The session gets what your pushed branch holds. After `outcomebound adopt`, that is the committed
install: the `AGENTS.md` block, the pointer file where the harness needs one, the guidance under `.outcomebound/fragments/`
and the skill folders.

The session does not get:

- the `outcomebound` command. No page says that any cloud environment holds it.
- the folders that Git ignores, so not `.agents/work`, `.agents/handoffs` or
  `.agents/shared-memory`, and not your worktrees.
- the research clone, which `outcomebound research` keeps once for each machine. The verb then
  names the public link instead.
- your personal files and memory. For Claude Code on the web, the user-level Claude files in your
  home folder do not load ([page](https://code.claude.com/docs/en/settings)).

Whether each harness loads the committed skill folders in a cloud session is shown for Claude Code
on the web only: its page says the repository's `.claude/skills` load
([page](https://code.claude.com/docs/en/skills)). For Codex cloud, Copilot and Cursor it is
`UNVERIFIED`. The Codex cloud page says the agent uses `AGENTS.md` for lint and test commands
([page](https://learn.chatgpt.com/docs/environments/cloud-environment)). The Copilot reference says
its cloud agent supports `AGENTS.md`
([page](https://docs.github.com/en/copilot/reference/custom-instructions-support)). The Cursor page
says its cloud agents read `AGENTS.md` ([page](https://cursor.com/docs/cloud-agent)). Claude Code on
the web loads the repository's `CLAUDE.md`, which the install points at `AGENTS.md`
([page](https://code.claude.com/docs/en/claude-code-on-the-web)); whether it reads `AGENTS.md` by
itself there is `UNVERIFIED`.

## The install line

`outcomebound adopt` prints a short cloud note, on an install, a dry run and `--check`. It writes no
file for it. The note holds this line, with the version of the engine that you install:

```bash
uv tool install outcomebound==<version>
```

Where `uv` is not there, the fallback is `python3 -m pip install outcomebound==<version>`. Add the
line to the setup step of your cloud environment. Where your project records a `Setup` fact, record
the line there too, so that a person with a fresh clone runs the same steps: run
`outcomebound adopt . --setup` again, repeating each recorded command and adding the line. Do not
edit the `Setup` line in `AGENTS.md` by hand, because `adopt` owns that block.

The package index must be reachable from the setup step:

- Claude Code on the web: the default network level allows the package index
  ([page](https://code.claude.com/docs/en/cloud-environments)).
- Codex cloud: the setup script runs with internet access; the agent phase after it blocks internet
  access by default ([page](https://learn.chatgpt.com/docs/environments/cloud-environment)).
- GitHub Copilot: the page says the firewall does not cover setup-step processes
  ([page](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-firewall)).
  Whether the package index is reachable by default is `UNVERIFIED`.
- Cursor: the pages do not say. `UNVERIFIED`.

## Where each harness keeps its setup step

The table is in `adapters/cloud.json`, with the page and the read date of each row.

| Harness | Setup step | Page, read 2026-10-17 |
| --- | --- | --- |
| Claude Code on the web | the cloud environment's setup script | [cloud environments](https://code.claude.com/docs/en/cloud-environments) |
| Codex cloud | the environment's setup script | [cloud environment](https://learn.chatgpt.com/docs/environments/cloud-environment); the page says a newer guide replaces it, and that guide was not found |
| GitHub Copilot | `.github/workflows/copilot-setup-steps.yml`, one job named `copilot-setup-steps`, read from the default branch only | [customize the agent environment](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment) |
| Cursor | `.cursor/environment.json`, the `install` key, built from the default branch | [setup](https://cursor.com/docs/cloud-agent/setup) |

`adopt` writes none of these files. The harness's maker owns each format and changes it, and a
hook or a vendor file written by the engine would be one more thing to keep current. For Claude
Code on the web, the page says that a setup script which runs longer than about five minutes is not
cached, so keep the setup step short.

## Decision briefs draw in plain form

In a cloud session of Claude Code on the web, `outcomebound brief` draws its diagram in the plain
(ASCII) form. It finds the session from the variable `CLAUDE_CODE_REMOTE`, which the page says is
`true` there ([page](https://code.claude.com/docs/en/cloud-environments)), and from the row for it in `adapters/surfaces.json`. No page shows whether the web view draws Mermaid, and no
one has observed it, so the form stays plain. An unknown surface draws plain too.

If you see Mermaid drawn in your view, set `OUTCOMEBOUND_DIAGRAMS=mermaid` in the environment, or
pass `--form mermaid`. Either one outranks the table.

## Handovers go in the pull request

A handover file in `.agents/handoffs/` stays on one machine, so a cloud session cannot read yours
and you cannot read its file. A cloud session puts its handover in the pull request description:
what landed with each check's verdict, what is in flight, what is blocked, and the next step. The
next session, cloud or local, reads the description with the branch.

## Not covered

- Google Jules: the pages read did not show its network, secrets or delivery. `UNVERIFIED`.
- Checks that need a list kept outside the repository, such as `make scrub` in this repository,
  read `UNVERIFIED` in a session that does not hold the list.
- A routine, which runs with no person to answer a decision brief. The page says a routine runs
  without stopping for approval ([page](https://code.claude.com/docs/en/routines)); what a hold
  does there is `UNVERIFIED`.
