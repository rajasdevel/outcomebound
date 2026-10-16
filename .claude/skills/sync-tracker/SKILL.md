---
name: sync-tracker
description: Use when reading a card from a tracker that is not the project's ticket store, or writing back to it. An example is a client's Jira. A read is a markdown snapshot; a write goes under a grant that names its kind, its notifications and automations, and its conflict rule, and any other write is a decision brief.
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

Save the card as a markdown snapshot, under one file name that stays the same for this card, with:

- the card's key and its fields, each under its own heading;
- the time the tracker says the card was last updated;
- each comment under its own heading that holds the comment's id, with its author and time (the
  importer makes one item for each heading, so a comment kept under a shared heading would hide a
  new one);
- the links to other cards;
- the ids of the attachments, and their names.

Import the snapshot with `outcomebound sources import --converted`, under the same `--name` each
time you read this card. Then a field that changed since the last read shows as a changed item, and
a new comment as a new one, and `gather-requirements` accounts for each. A snapshot cannot show that
it is current: it is the card as of the time you read it, and says so.

The snapshot holds the client's text. Keep it out of the repository unless the project says otherwise,
and do not paste it into a public place.

## Write to a card

Check what each kind of write does to the people who use the tracker, in this tracker, with this
project's automations. A standing grant covers a write only when it names three things: the kind of
write, the notifications and automations that write is known to start, and the conflict rule (what
happens to a change someone else made since you read the card). A request for one named write in
this session covers that write once you have shown the text. Any other write goes as a decision
brief, with the old text, the new text, what it is known to start and what is `UNVERIFIED`.

- A **comment** commonly notifies the card's watchers. A grant for comments in batches covers them
  when it says that they notify and who is told.
- A **description write** commonly replaces the whole field, and a tracker may hold no lock, so
  a change made by someone else since you read it can be lost. A grant covers it only when it
  states the conflict rule, such as writing only if the updated time is unchanged.
- A **status transition** can start the client's workflow automations, which may notify people,
  assign work, or close related cards. A grant covers it only when it names what the transition
  starts.

Authority to read is not authority to write, and a grant for one kind of write is not a grant for
another.

Before each write, read the card's updated time again. If it moved since your snapshot, import a new
snapshot and look at what changed before you write. That read cannot catch a change made after it:
where the tool can make the write conditional on the version or updated time, do so; where it
cannot, write only where the grant accepts that race, else give the person a draft. Unless a
standing grant covers this kind of write, show the person the exact text first; under a batch
grant, show the text once for the batch.

After each write, read the card back and compare it with what you wrote: the text, the author, and
the updated time. A write whose read-back you did not make is `UNVERIFIED`.

Keep a receipt for each write: the card, the text, the account that acted, the time, and the
words of the grant that covered it. The acting account is the person's own account unless they have
given you another; say which.

Where the tracker answers that you are sending too fast, wait as long as it says, with one call in
flight at a time, and read the card back before you send again: the first call may have succeeded.
Where the read-back shows its effect, keep its receipt and do not send again; where it cannot tell,
do not send again, and say why.

Where access is denied, or the harness has no tool that writes to the tracker, do not look for
another way in. Write a draft file with the text and the card it belongs to, and give it to the person
to paste.
