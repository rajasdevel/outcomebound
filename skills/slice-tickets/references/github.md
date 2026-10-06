# The `github` store: declaring it, and publishing to it

In the `github` store a ticket is an issue of the declared repository carrying the ticket label,
and publishing is creating it. Every verb reads an export you produce first and pass as
`--input`; produce it again after any write of your own, since a report answers about the
export it was given:

```sh
gh api graphql --paginate --slurp -F owner=<owner> -F name=<project> \
  -F query=@<home>/templates/tickets/github-export.graphql > issues.json
```

`<home>` is the folder `outcomebound home` prints, in forward slashes; `outcomebound tickets
export` prints the line with it filled in. The same line runs in a POSIX shell, PowerShell and Git
Bash, since `gh api` reads a field that starts with `@` from that file. The verbs read the export as
UTF-8, with or without a byte-order mark, or as UTF-16 with a byte-order mark, which Windows
PowerShell 5.1 writes for `>`. This line has not been run in PowerShell on Windows (`UNVERIFIED`).

The verbs refuse a file that is not this query's `--paginate --slurp` output for the declared
repository.

## The store brief

Before a declaration exists, look up the tracker's labels with
`gh label list --repo <owner>/<project>`, so a name collision is known before the question is
asked. Then put the store and the three label names to the user as one decision brief, drawn as
the `decision-brief` skill says: recommend the `github` store and the shipped names `ob-ticket`,
`human-only` and `human-requested`, give the lookup's result, and say that a yes to the tracker
store grants tracker writes in this repository, so a single yes chooses the store and the names
and grants the writes. It is drawn as the `decision-brief` skill says and names the writes the
yes grants, so the person's reply can state them; a letter alone grants nothing. Where a chosen name exists with another meaning, say so and recommend a free
alternate; never repurpose a label. Where the lookup itself cannot run, say so and ask for the
names rather than recommending them as free.

Each label means one thing. The ticket label makes an issue a ticket, and applying it is the
user's acceptance, which no later edit lapses. The hold label says a person holds the ticket and
agents leave it. The request label says an agent is asking a person to take the ticket, and only
an agent applies it.

On the yes, and only then: create the labels,

```sh
gh label create <label> --repo <repo> --description "an issue is a ticket when it carries this; applying it is the user's acceptance"
gh label create <human_label> --repo <repo> --description "a person holds this ticket; agents leave it"
gh label create <request_label> --repo <repo> --description "an agent is asking a person to take this ticket"
```

write `.outcomebound/tickets.json` with the chosen names, the `writes` entry naming the person
and the date of their word, and `claims` naming the project's committed validation plan,

```json
{"version": 1, "store": "github", "repo": "<owner>/<project>",
 "label": "<label>", "human_label": "<human_label>", "request_label": "<request_label>",
 "claims": ".outcomebound/ticket-claims.json",
 "writes": {"granted_by": "<their username>", "on": "<the date of their yes>"}}
```

and commit the declaration alone, the message quoting what they said. Where the project has no
validation plan yet, commit `{"version": 1, "cwd": "..", "claims": []}` at the `claims` path in
the same commit; the tickets add claims to it. A relative `cwd` starts at the plan file's folder,
so `..` runs the claims of `.outcomebound/ticket-claims.json` at the checkout's root. Without
the yes: create nothing, write no `writes` entry, commit nothing, and print the three commands
and the declaration for a person; a person who chooses the store but withholds the grant gets the
same.

## Publishing

`outcomebound tickets publish --draft <file>...`, given every accepted draft, prints a POSIX
shell script that publishes them with `gh`, and runs nothing itself. It runs `check --draft` on
the drafts first and refuses with `PUBLISH_REFUSED` where that reports an error. The script
creates the issues in an order that lets each relation name an issue that exists, sets each
issue's `--parent` and `--blocked-by` as it creates it, applies the ticket label, and the hold
label to a draft with `human-only: yes`, and writes each body as the draft without its
`# <title>` line, which becomes the title, and without the `blocked-by` and `parent` lines of its
block, which the tracker holds. A `discovered-from` naming a sibling draft becomes that draft's
issue number; a sibling's name in a body's prose is left as written.

Run the script only where the declaration records the `writes` grant, which its header names;
otherwise print it for a person and report the breakdown as waiting on them. A `gh` that lacks
the relation flags fails on them: print each relation for a person, and name it in the report
as not set, since agents read what can start from these relations. The ticket label is
applied at creation, to the issues the user accepted in the breakdown and to a follow-up a goal
envelope's Follow-ups line accepts, and to nothing that already exists; removing it is the user's
act alone. Where a command fails, produce the export again to see what was created, and run again
only what it shows missing. Where it fails again, stop publishing, print what is left for a
person, report those tickets as waiting on them, and go on with the work that does not depend on
them. Produce the export again after the last write, and run `check --input issues.json` on it.
