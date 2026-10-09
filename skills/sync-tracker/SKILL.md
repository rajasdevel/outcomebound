---
name: sync-tracker
description: Use when reading a card from a tracker that is not the project's ticket store, or writing back to it. An example is a client's Jira. A read is a markdown snapshot; a write is a comment under a grant, and each other write is a decision brief.
---

# Sync a tracker

You are done when each card you read is a snapshot that the sources verbs can compare, and each write
you made is read back and has a receipt. The tracker belongs to someone else, often a client, and
its people see what you write. The engine holds no credential and calls no service: every read and
write goes through a tool the person has already signed in to.

The project's own tickets are not this tracker. Link a card and a ticket; do not copy one into the
other, so that neither holds a stale copy of the other.

## Read a card

Read through the harness's connector, a command-line tool the person has signed in to, or an export
the person gives you. Do not ask for a password or a token, and do not look for one.

Save the card as a markdown snapshot with:

- the card's key and its fields, each under its own heading;
- the time the tracker says the card was last updated;
- the comments, each with its author, time and id;
- the links to other cards;
- the ids of the attachments, and their names.

Import the snapshot with `outcomebound sources import --converted`, under the same `--name` each
time you read this card. Then a field that changed since the last read shows as a changed item, and
a new comment as a new one, and `gather-requirements` accounts for each. A snapshot cannot show that
it is current: it is the card as of the time you read it, and says so.

The snapshot holds the client's text. Keep it out of the repository unless the project says otherwise,
and do not paste it into a public place.

## Write to a card

Check what each kind of write does to the people who use the tracker.

- A **comment** is mailed to the card's watchers. A standing grant can cover comments, in batches,
  and only a grant that names that each comment notifies the watchers covers them. Without that
  wording, a comment is a single act that the person approves.
- A **description write** replaces the whole field, and the tracker holds no lock: a change made
  by someone else since you read it is lost. It is a decision brief each time, with the old text,
  the new text and the time you read it.
- A **status transition** can start the client's workflow automations, which may notify people, assign
  work, or close related cards. It is a decision brief each time, naming what the transition
  is known to start and what is `UNVERIFIED`.

No standing grant covers any other write. Authority to read is not authority to write, and a
comment grant is not a grant to change a field.

Before each write, read the card's updated time again. If it moved since your snapshot, import a new
snapshot and look at what changed before you write. Show the person the exact text you will write.

After each write, read the card back and compare it with what you wrote: the text, the author, and
the updated time. A write whose read-back you did not make is `UNVERIFIED`.

Keep a receipt for each write: the card, the text, the account that acted, the time, and the
words of the grant that covered it. The acting account is the person's own account unless they have
given you another; say which.

Where the tracker answers that you are sending too fast, wait as long as it says and send again
with one call in flight at a time. Before any retry, read the card back: the first call may have
succeeded.

Where access is denied, or the harness has no tool that writes to the tracker, do not look for
another way in. Write a draft file with the text and the card it belongs to, and give it to the person
to paste.
