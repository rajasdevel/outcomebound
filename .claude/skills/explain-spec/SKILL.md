---
name: explain-spec
description: Use when a person must act on a spec they did not write, or says they do not follow it. Explains the spec, asks questions drawn from its decisions, and fixes or records what the answers show is missing.
---

# Explain a spec

You are done when you have explained the spec to the person, each misunderstanding that could
change what they do has been examined, and each real gap in the spec is fixed in it or recorded
in it. You never report that the person fully understands the spec: you report what you
explained, what they answered, and what changed in the spec.

## Explain

Read the spec and the code it points to, and teach only what they say; mark anything else
`UNVERIFIED`. Start from what the person says they already know and skip it. Give the outcome
and who it is for, then each decision in dependency order with the alternative the spec rejected
and the reason, then the edges: what happens when the input is empty, the call is repeated, a
step fails, or the change is undone. Where order or flow is the point, add a diagram, in the form
the surface shows. Write for the person in the style the project sets for text people read; when
a message does not land, say it again, shorter, in the project's own terms.

## Ask

Draw the questions from the spec's rows, not from your own idea of what matters: for each
decision with a rejected alternative, "why not" that alternative; for each assumed row, what is
assumed and what would reverse it; for each edge, what happens. Ask for a prediction or an
answer and wait for it; reading the explanation back is not understanding. Make the options of a
multiple-choice question equal in length so the format gives no clue. Where trying a mechanism
teaches more than reading about it, or the questions are many, the explanation and the questions
can go in an explorable (the `explorable` skill), whose reply brings the answers back.

## What a wrong answer means

When the spec does not answer the question, the gap is real: fix the spec in place, or record the
row as open, in the same change. When the spec answers it and the person did not follow, explain
that row again and ask again; where the row's words caused the misreading, fix the words in the
same change.

## With no person present

A run with nobody to answer cannot show understanding, so report `UNVERIFIED` for it. Write the
map and the questions to the working area, with the rows most likely to be misread, so a later
session starts there, and go on with the rest of the work; this skill blocks nothing.
