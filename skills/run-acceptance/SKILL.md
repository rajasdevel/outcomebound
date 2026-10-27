---
name: run-acceptance
description: Use when preparing, running or recording acceptance of a delivered change by a person outside the build. The agent prepares and pre-runs; a person accepts.
---

# Run acceptance

You are done when the acceptor can give or withhold acceptance of the delivered change: they have
scripts they can follow in their own words, each script has been pre-run on the build the
environment serves, and a draft record waits for their verdict. You do not give acceptance. Your pre-run shows that a script can be followed
and what it did; it is not acceptance, and the record says so.

Acceptance is by someone outside the build: a client, a business user, a tester who did not write
the change. Your own tests, and a review by the people who built it, are other checks. For a change
that has no such acceptor, this skill does not apply.

## Write the scripts

Take the examples the spec holds, each rule with its concrete cases. Where the spec has no examples
for a criterion, write them with the person who owns the criterion before you write a script.
Then write each script in the acceptor's words: the screens, the names and the steps as they use
them, with the starting state, what to do, and what they should see. A script names no code, no
command and no internal id they would not know. What only the person who sets up the session needs,
such as commands, paths and the build check, stays out of the scripts and out of the folder that
holds them; it goes in the draft record.

Make a table from each acceptance criterion to the scripts that cover it. A criterion with no script
is a gap; say so rather than adding a script that touches it by name.

## Read the build

An environment may serve more than one build or flag state, by route, by user group or by flag, and
what it serves may not be the one you expect. Before you run or hand over a script, read which build
the environment serves: the version, commit or build id it reports about itself, from the environment
and not from the pipeline's log, and the service versions and the flag or configuration state that
the script exercises. Read them again after the run. Two reads cannot show a change and back
between them: pin the build or route where the project can; else keep the build each response
names with its result; else say in the record that the build between the two reads is
`UNVERIFIED`. Identity is what the artifact is: a digest or
a version for a delivered file or a library, the environment's own report for a service. Where the
environment does not report it, say so; the build is then `UNVERIFIED`, and so is every result. A
run during which the build or the state changed, or that reached a mix of them, is `UNVERIFIED`:
run it again.

## Pre-run

Run each script on that build, in the environment the acceptor will use, one step at a time as the
acceptor will follow it: each step its own plain command or action, and each read of the build its
own command before and after, never folded with the steps into one program of your own. Keep the
evidence for each result: the output, a screenshot, or the response, with the build it ran on. A script that cannot
be followed as written is a defect in the script: correct it, and run it again. A script that
fails is a defect in the change: it is not handed to the acceptor until the defect is dealt with or
the acceptor is told of it.

State plainly, in the record and to the person, that this was a pre-run by the agent and that it
is not acceptance.

## The record

Draft the acceptance record with these fields:

- the build identity, and the environment it was served from;
- the service versions and the flag or configuration state each script exercised, as read around
  the run;
- each script, with the result of the pre-run and the evidence;
- the setup the pre-run needed: the commands, the paths and how the build was read, for the person
  who sets up the session;
- who accepted, in their own words: what they said or wrote, quoted, and not a summary;
- when they accepted.

Leave the last two fields empty until the person has given acceptance. Do not fill in a name from an
account, a login or a guess. The record is kept where the project keeps it: in a committed file,
or in the tracker through the `sync-tracker` skill, where a draft record is a write like any other.

The limit of this skill is stated here so that no reader takes the record for more. The agent drafts
the record and a person gives the acceptance. The engine cannot tell who gave it, and neither can you.
A record that names a person is evidence of what the record says, not of who typed it.

## Defects

A defect that keeps the change from meeting its own criterion is corrected inside the change; the
build it produces voids the acceptance for what it touches, and those scripts run again. A defect
outside the change becomes a ticket of its own, with the script, the step, what was expected, what
happened, and the build. Do not drop a defect because the acceptor accepted anyway: record that
they accepted with the defect known.

## A screen

Where the criterion is a screen, put the design frame and the built screen side by side, at the
same state and the same size, and let the person judge whether they match. You can list the
differences you see; you do not decide that a difference is acceptable. States the design does
not show are marked as not shown.

## A later build

Acceptance is of a build. A later build voids the acceptance for the changes it touches: name those
changes and say that they need acceptance again. A later build that touches nothing the accepted
scripts reach may keep it, but only when you say how you know. Where the project promotes a built
artifact, the accepted artifact is promoted unchanged and a release commit only labels it. Where it
deploys from source at a tag, a tagged commit that is a child of the accepted commit keeps the
acceptance only when its diff, read by you, touches only the version and changelog files; the record
names both commits and the diff check, and a script that checks the reported version runs again on
the release build. Never carry an acceptance forward by changing the build identity in the record.
