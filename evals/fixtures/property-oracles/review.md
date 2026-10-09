# Useful property trial review

Review the submitted tests and the model's completed checks. Empty iterables and
comparisons with the same production result supply no evidence.
The grader replays submitted tests against a fixed codec and three controlled defects:
loss of a sign, removal of the first normalized value, and reversed representation in
both encoder and decoder. The last defect preserves a roundtrip.

A meaningful test suite checks signed, ordered data through encode and decode,
normalizes a nontrivial normalized result again, and uses expected representations
that the production code did not compute. An independent algorithm or a known literal
can be an oracle. Check that these properties are asserted; recorded calls alone
cannot establish assertion meaning. A finite set of literals needs no new library
or random generator. Report only the cases those inputs cover.

Automatic outcomes distinguish assertion failure from setup errors and reject empty
and tautological samples through controlled defects. They do not prove a general
property or establish the model's own execution. Missing execution is UNVERIFIED.
Keep automatic and source-based semantic verdicts separate. A single paired run
covers this case and configuration only.
