# A private kit

You have skills, scripts and habits that apply to many projects, and that no project should
carry. An example is a script that updates a cloud firewall rule when your public IP changes.
Its rule names, account ids and log belong to you. If they enter a project's files, they enter
its history, its clones and its pull requests.

OutcomeBound gives no verb for this. A guide is enough, because each harness already reads a
user-level folder that no project sees. This guide shows how to keep one private repository, the
kit, and link it into those folders.

## What the kit holds

Make a private Git repository. Never give it a public remote. Keep it outside every project.

```text
kit/
  skills/<name>/SKILL.md   one folder for each private skill
  tools/<name>             scripts that a skill tells an agent to run
  pointer.md               when to read what (see "The pointer file")
  config/                  your private values: names, ids, lists (never credentials)
```

A skill's `description` is its trigger. An agent reads the descriptions of all linked skills and
opens a skill when its description fits the task. So a skill needs no entry in any project.

## Link the kit

Link to the user-level folders only. Never link or copy into a project.

| Harness | Skills folder | User instruction file |
| --- | --- | --- |
| Claude Code | `$HOME/.claude/skills/<name>/SKILL.md` | `$HOME/.claude/CLAUDE.md`, `$HOME/.claude/rules/*.md` |
| Codex | `$HOME/.agents/skills` | `$HOME/.codex/AGENTS.override.md`, else `$HOME/.codex/AGENTS.md` |
| Cursor | `$HOME/.agents/skills`, `$HOME/.cursor/skills`, and `$HOME/.claude/skills` | User Rules in the settings screen only; no file path is documented |

Sources, read 2026-10-17: the Claude Code documentation pages `memory` and `skills` at
code.claude.com/docs/en; the Codex pages `agent-configuration/agents-md` and `build-skills` at
learn.chatgpt.com/docs; the Cursor pages `context/rules` and `context/skills` at
cursor.com/docs. The Codex pages say that Codex follows a symlinked skill folder. The Cursor
skills page lists `$HOME/.claude/skills` as a folder it reads, so Cursor finds the kit through
either link. Which one wins when the same name is in two folders: the Cursor page does not say
(`UNVERIFIED`).

Set `KIT` to the kit's folder. On macOS and Linux:

```bash
KIT="$HOME/private-kit"
mkdir -p "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.claude/rules" "$HOME/.codex"
for s in "$KIT"/skills/*/; do
  n=$(basename "$s")
  ln -sfn "$KIT/skills/$n" "$HOME/.claude/skills/$n"
  ln -sfn "$KIT/skills/$n" "$HOME/.agents/skills/$n"
done
ln -sfn "$KIT/pointer.md" "$HOME/.claude/rules/kit.md"
```

`ln -sfn` replaces a link that exists, so you can run the loop again after you add a skill.
Edits to a skill in the kit show at once, because the link is the file.

For the Codex instruction file, check first: `ls -l "$HOME/.codex/AGENTS.md"`. If you have the file
already, add one line to it by hand that tells Codex to read `$KIT/pointer.md`. Do not replace
your file with a link. If you have no such file, `ln -s "$KIT/pointer.md" "$HOME/.codex/AGENTS.md"`
works. Codex reads `AGENTS.override.md` first when it exists, so a link in `AGENTS.md` is then
not read.

Check the links:

```bash
ls -l "$HOME/.claude/skills" "$HOME/.agents/skills"
test -e "$HOME/.claude/skills/<name>/SKILL.md" && echo resolves || echo dangling
```

A link whose target moved is dangling, and the harness sees no skill. The check above shows it.

### Windows

A Windows symlink needs Developer Mode or an administrator shell (`UNVERIFIED` here: not run on
Windows for this guide). In PowerShell:

```powershell
New-Item -ItemType SymbolicLink -Path "$HOME\.claude\skills\<name>" -Target "$KIT\skills\<name>"
```

If that fails, copy instead: `Copy-Item -Recurse "$KIT\skills\<name>" "$HOME\.claude\skills\"`.
A copy does not follow your edits. Copy again after each change, and keep the kit as the one
source.

## The pointer file

`pointer.md` tells the agent in general terms when to read the kit. Example:

```text
My private kit is at $HOME/private-kit. When a task matches a skill in it, use that skill.
Before you run a tool from the kit, read the tool's skill. Never write a name, id or path
from the kit into a committed file of any project.
```

Put it in the user files in the table: a link to `$HOME/.claude/rules/kit.md` for Claude Code, and
one line in `$HOME/.codex/AGENTS.md` for Codex. Both documentation sets say that user instructions
are loaded together with the project's. They are added to it, and they do not replace it
(sources as above). Do not put this text in a project's `AGENTS.md`: that file is committed.

## Cloud sessions see none of it

A cloud or background session starts from the pushed branch. The Claude Code documentation
(`cloud-environments`, read 2026-10-17) says that the user's `$HOME/.claude/CLAUDE.md`, skills,
user-scope plugins, user MCP servers and user hooks are not available there. The Cursor
documentation says that user hooks are not available in cloud agents, and that only
`$HOME/.cursor/skills` can sync, with a setting turned on. For Codex cloud the documentation read
for this guide does not say whether `$HOME/.codex` or `$HOME/.agents` apply (`UNVERIFIED`).

So write each machine-bound tool to refuse to run away from your machine. A cloud session has
no sign-in of yours, and its network address is not yours. A tool that updates a firewall rule
for "my IP" would put the address of the cloud machine in the rule.

A simple check, for a tool written in shell, is to require a marker file that only your
machine has:

```bash
[ -f "$HOME/.private-kit-machine" ] || { echo "refused: not my machine" >&2; exit 2; }
```

Create the marker once, by hand, on each machine where the tool may run. Keep the check as the
first line of every tool that acts outside the machine.

## A tool that acts outside the machine

Take a script, `tools/rule-sync`, that sets the source address of one firewall rule to your
current public IP. It acts outside the machine, so it follows these rules.

1. **Ask for a grant first.** Changing a live firewall rule widens who can reach a service. Tell
   the agent, in the tool's skill, to stop and ask you before the change. Your grant names the
   rule, the largest address range (one address), and "this address only". Deleting the old
   address, and a scheduled run with no one present, are separate grants.
2. **Dry run is the default.** With no flag, the tool reads the current rule and the current IP,
   prints the exact command it would run, and changes nothing. A flag such as `--apply` makes
   the change. After it, the tool reads the rule again and prints the result.
3. **Log each run.** Append the time, the rule, the old value and the new value to a log file in
   the kit's folder or in `$HOME/.local/state`. Never log to a project. Keep the log out of Git
   with the kit's `.gitignore`.
4. **Keep credentials out of the kit.** The tool uses the sign-in you already made with the
   cloud provider's command line, or your secret store. The kit holds no password, key or token,
   and the agent never types one. A private repository is still a repository that can be cloned,
   shared by mistake or read by a service.
5. **Refuse away from your machine** (the section above).

## Keep private names out of project files

The kit helps only if its names stay in the kit.

- The pointer and the skills sit in user-level files, so no project needs a line about them.
- Put your private values (rule names, account ids) in `config/` in the kit. A tool reads them
  from there. A skill says "read the config", and does not copy the values.
- Make a list of your private names in a file outside every repository, and scan commits with
  it before you push. This repository's `make scrub` does that with the file that `OB_SCRUB_LIST`
  names; use the same idea in your own projects.
- Do not run `outcomebound adopt` with the kit's names in a fragment or in `local.md`. Those
  files are committed.
