---
name: land-change
description: Use when driving a pull or merge request through CI and review to landing. Covers the handover, a failing check, each review comment, the merge and where the agent's authority over other people's reviews ends.
---

# Land a change

You are done when the request has landed under a grant that covers it, or waits on a named person
for a named reason. Each check has a verdict, each review thread has a reply, and no person's review
was resolved, approved or dismissed by you. A request that no one has reviewed and that no check
gates needs only the handover and the merge grant.

## The handover in the request

The request description is the record a reviewer reads without you. It holds:

- what changed, and why, in the words of the outcome and not of the diff;
- each check the completion bar names and its verdict, `PASS`, `FAIL` or `UNVERIFIED`, with the
  command for a verdict a reader may want to repeat; a check that failed is always listed, and a
  check nobody asked for is not;
- what you decided that the ticket did not settle, so that the reviewer can overrule it;
- the follow-ups: what you saw and left alone, each with where it is recorded.

Update the description when the change moves, so that it describes the tip and not the first push.

## A failing check

A failure of CI is a failure with an unknown cause until you have read its log. Follow the
`diagnose` skill: reproduce it where you can, find the cause, fix that. A check that fails on the
base branch as well is pre-existing: say so in the request and do not fix it inside this change
unless the ticket owns it. Never mark a check green by retrying it until it passes, by skipping
it, or by loosening what it checks; a flaky check is reported as flaky, with its runs.

## A review comment

Treat each comment as a finding and follow the `review-findings` skill. Then act by what the comment
is:

- A clear defect or a clear request that fits the ticket: fix it, push, and reply with the commit
  and what it changed.
- A comment that is ambiguous, or asks for a change of design or scope: do not choose for the
  reviewer. Put the question to the person who owns the decision, with the options you see, and say
  in the thread that you have asked.
- A comment you check and find wrong: reply with the evidence, and leave the thread open for its
  author.

Every thread gets a reply that names the commit that answers it, or says why there is none. Read the
replies of the person after each push, because a comment can change what an earlier one meant.

Authority over review ends where another person's judgement begins. You do not resolve a thread
another person opened, approve a request, dismiss a review, or mark a requested change as done on
their behalf: the author of a thread, or the person who owns the review, does that. A review you
wrote yourself, or one by another agent that works for the same person, is a check on the code and
not a second party's review. Where the project requires a second party, it is still missing.

## When the rounds do not converge

After each round of fixes, count the findings that have a verified disposition: a fix pushed and
replied to, or a reply with evidence that the comment is wrong. Do not count thread closures, since
a thread another person owns stays open until they close it. A thread that waits on its reviewer
waits; it is not a failed repair. Ask the person, naming the findings and what you tried, when a
round gave no finding a verified disposition, or a finding comes back or the reviewer and you
disagree after the same reply. When a finding you marked fixed comes back, find why first. Where a
later change undid the fix and the cause is plain, repair it inside the task with its regression
check, and say the cause in the thread. Where the fix did not hold, or the finding comes back again,
the assumption behind the fix is wrong: ask the person. More rounds of the same kind of fix repeat
that assumption.

## The merge

Merge only where a grant covers this merge, in this repository, by this method. A grant to open
a request, or to push to the branch, is not a grant to merge. Before the merge, read the request
again: the checks on the tip you are merging, the required reviews, and a conflict with the base.
A merge can start a deploy, a release or a publish. That is inside the grant only where the grant
names it; otherwise report that the merge will start it and hold the merge, as a decision brief
(`decision-brief`). A merge grant is not a tag grant: where the release act is a tag push and not
the merge, the merge grant does not cover the tag. After the merge, read the result: the merged commit, and that the checks
of the base branch for that commit are the ones the project depends on. A merge is not a deploy
and not an adoption downstream.

## The route part

Where the project's `local` fragment names streams and gates, the request also holds:

- the card and the requirement ids the change serves;
- the build identity: the commit, and the artifact built from it where there is one;
- the door: whether the change can be undone, and how;
- the blast radius: who and what the change reaches if it is wrong;
- what was not checked, as `UNVERIFIED` lines.

A request into the production stream follows the project's promotion model (the `deploy`
fragment): where the project promotes accepted builds, it holds only the commit that was accepted
for that stream, with nothing added since and no fix folded in, and a change added after acceptance
goes back to the stream that accepts it. Where the project promotes a built artifact, the
accepted artifact is promoted unchanged and a release commit only labels it. Where it deploys from
source at a tag, the tagged commit may be a child of the accepted commit whose diff, read by you,
touches only the version and changelog files, and the record names both commits; any other change
goes back. Behind a feature
flag, the flag's state is part of what was accepted. An emergency follows the project's emergency
route: the production go first, and, where that route puts them after the promotion, the review
and acceptance after it.
