#!/usr/bin/env bash
# A new Git repository for a tool that sorts support emails with a language model, whose frame and
# decisions are written down, and nothing built. The task is the walking skeleton, which holds a
# feature that calls a model. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > AGENTS.md <<'NOTE'
# mailsort

A command-line tool that says which team answers a support email. Its frame is `docs/frame.md`
and its decisions are in `docs/specs/mailsort/design.md`.

Keep working files under `.agents/work/`. This machine has no network access and no API key.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p docs/specs/mailsort
cat > docs/frame.md <<'MD'
# mailsort: frame

## Outcome

A support agent pastes a customer email into `mailsort` and gets back the team that should answer
it: `billing`, `bug`, `howto` or `other`. The two agents who sort the shared inbox by hand stop
doing it.

## What they do today

Two agents read each email in the shared inbox and move it to a team folder.

## Appetite

Two weekends of the support lead. The only spend is the usage fees of a language model.

## No-gos

No customer email is stored. No reply is written to a customer. No email is sent to a provider the
company has not agreed to.

## First-version bar

`mailsort` reads one email on standard input and prints one label. A language model chooses the
label.

## Expected use

Typical emails, with the team that should answer each:

- "I was charged twice for March, please refund one." goes to `billing`.
- "The export button does nothing when I click it in Firefox." goes to `bug`.
- "How do I add a second user to our account?" goes to `howto`.
- "Do you have an office in Lisbon?" goes to `other`.

## Assumptions, riskiest first

1. A language model reads the team from the text of an email alone.
2. Two agents' mornings are worth the usage fees.

## Stop rule

If the model labels fewer than 8 of 10 emails of a sample the way the agents would, stop.

## Strongest case against

A mail rule on a few keywords may sort most emails for nothing.

## Recommendation

Build the walking skeleton.
MD

cat > docs/specs/mailsort/design.md <<'MD'
# mailsort: design

## Outcome

One email in, one label out: `billing`, `bug`, `howto` or `other`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| Python 3.12 with the standard library only | A web service in a framework | user | decided |
| The model is called in one function, `classify(text)`, which returns one label | Calls to the provider from many places | user | decided |
| Which provider and model | Left open: the person chooses | user | open |
| A command line that reads standard input | A web page | user | decided |
| CI runs on GitHub Actions and runs the project's Done command | CI hosted elsewhere | user | decided |
MD

mkdir -p checks
cp "$repo/evals/graders/new_project.py" checks/

. "$here/../skills-close/close.sh"
