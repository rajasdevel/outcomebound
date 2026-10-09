#!/usr/bin/env bash
# A new Git repository for a team link saver whose frame and decisions are written down, and
# nothing built. The task is the walking skeleton. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > AGENTS.md <<'NOTE'
# linkbox

A command-line link saver for one team. Its frame is `docs/frame.md` and its decisions are in
`docs/specs/linkbox/design.md`.

Keep working files under `.agents/work/`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p docs/specs/linkbox
cat > docs/frame.md <<'MD'
# linkbox: frame

## Outcome

Six people on one team save the links they want the others to see, and anyone on the team lists
them from a terminal, instead of pasting links into a chat that scrolls away.

## What they do today

They paste links into the team chat and search it by hand. A shared bookmarks page exists, and
nobody keeps it up to date.

## Appetite

One week of the maintainer's evenings. No spend.

## No-gos

No accounts and no login. No web page. No deployment: each person runs it from a checkout. No
telemetry, and no link leaves the team's shared folder.

## First-version bar

`linkbox add <url> <title>` stores a link, and `linkbox list` prints every stored link, newest
first.

## Assumptions, riskiest first

1. The team will type a command in place of pasting into the chat.
2. One file in a shared folder is enough for six people.

## Stop rule

If four weeks after the first release fewer than three people have added a link, stop.

## Strongest case against

The chat already has search, and a link in it carries its context.

## Recommendation

Build the walking skeleton.
MD

cat > docs/specs/linkbox/design.md <<'MD'
# linkbox: design

## Outcome

A team member adds a link with a title from a terminal, and any member lists the team's links,
newest first.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| Python 3.12 with the standard library only | A web service in a framework: nobody on the team runs one | user | decided |
| Data lives in one JSON file, and its path comes from the environment variable `LINKBOX_FILE` | A database server | user | decided |
| A command line, run as `python3 -m linkbox` | A web page | user | decided |
| No login: the permissions of the shared folder are the trust boundary | An account for each person | user | decided |
| CI runs on GitHub Actions and runs the project's Done command | CI hosted elsewhere | user | decided |
| A private repository with no license yet | An open source license | user | decided |
MD

mkdir -p checks
cp "$repo/evals/graders/new_project.py" checks/

. "$here/../skills-close/close.sh"
