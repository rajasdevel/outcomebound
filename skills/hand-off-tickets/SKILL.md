---
name: hand-off-tickets
description: Use when handing an accepted ticket to the agent or model that will build it: finding the implementer's tier, and writing the package that tier needs, from the ticket alone for a capable model to failing tests and stubs, one step at a time, for a small one. Not for slicing work into tickets.
---

# Hand a ticket to its implementer

You are handing an accepted ticket to the model that will build it. The ticket stays as the person
accepted it; what you add is a package shaped by what the implementer can be trusted to decide.
The package says what the implementer is given, never how it works; the project's own gate decides
done at every tier.

**Done when** all four hold:

1. The hand-off names the implementer's tier and where it came from: the person, or the placement
   table at the commit its first line names.
2. The package carries what its tier's section below lists. Every existing path, symbol and command
   it names is in the tree as it stands when the package is written, and every one the work adds
   is marked as added.
3. At the spec tier, every test a step's package carries ran before the hand-off and failed for
   the reason it names.
4. At the spec tier, each step's result was reviewed by a model at the outcome tier, you where you
   are one, before the next step's package was written.

**Bounds.** Writing a package, with its tests and stubs, inside the ticket's `bounds` and on the
branch the ticket is built on, proceeds without asking. The ticket's outcome, `bounds` and
`done-when` stay the person's: a package adds to them and never changes them, and where the ticket
cannot be built as written, that goes to the person. The person does not accept a package, so it
decides nothing the ticket left to them.

## Find the tier

Use the implementer the person names now, or the one the slicing recorded in a comment on the
ticket; where neither exists, ask. Find its model and effort in the placement table
`outcomebound research models/tiers.md` prints, which says how an unlisted model or effort is
placed, and carry the notes its row gives into the package. Where that reports no clone, or
`outcomebound` is not on PATH, ask the person which tier the implementer is: outcome, design or
spec. A tier the person names directly stands.

## Outcome tier

The ticket as compiled by `outcomebound tickets brief <id> --input <export>`, plus only the lines
its row's notes give and the commands under "Hand over". No design, plan or tests: the implementer
designs, plans its milestones and writes its tests, and detail written for a less capable reader
narrows what it would have done.

## Design tier

The compiled ticket and its row's notes, plus:

- the approach chosen and, in one line, the alternative rejected;
- the signatures of the symbols the work adds or changes, with their types and how each fails;
- the data structures, and the invariants they keep;
- an edge-case table: the scenario, the expected result, and the test that proves the row by
  calling the real code path;
- a milestone plan, each milestone ending in a check the implementer can run.

The implementer writes the code and the tests.

## Spec tier

Cut the ticket into steps. A step is one behaviour whose tests you can write before it and see
fail, touching only the files the step names; where the implementer's row records a clean landing,
no step is larger. Write one step's package at a time, after the previous step is done: committed
on the ticket's branch with its tests passing, and reviewed. A package written ahead describes code
that will have changed. The ticket reaches the project's default branch at its last step, through
the project's gate, as any ticket does.

Each step's package is executable first:

1. Tests you wrote and ran on the ticket's branch, each failing before the step for the reason it
   names.
2. Stubs with the exact signatures, types and docstrings, in the files they belong in.

Then, in this order: the files the step may write; each existing symbol it uses, with its shape;
the algorithm and data structure to use, with a test that checks the bound where one matters;
any text a person or a record will read, verbatim; the edge cases the tests cover, and any they
leave out; the existing file whose shape to follow; and when to stop and report rather than
guess. State each instruction once, one instruction to a sentence: a small model drops
instructions under load, and stops where two of them disagree.

The package's tests are fixed: the implementer makes them pass and may add its own, and changes or
removes none of them. Say so in the package, naming the test files.

Where a step's package would be its code, write the code yourself and go on to the next step.

Review each step against its tests, its files and the ticket's `bounds`, and the last step against
the ticket's `done-when` as well. A step that fails review goes back once with the finding; one
that fails again you write yourself or hand to a higher tier, and the handover says which.

## Hand over

The package is a message to the implementer, or a file in the ticket's worktree that the message
names; it never goes into the ticket's body. Give the implementer the commands it needs: where to
work, how to run the tests, and what not to run. Commit as the project's `CONTRIBUTING.md` says.
The implementer's handover says what changed, each check's verdict, what it decided beyond the
package, and the follow-ups it found. When the ticket is done, your handover says the same for the
ticket, and names the tier and the implementer that built it.
