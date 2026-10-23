# reply-lean

**Question.** Does the reply hand over the table without a ledger of checks, method notes or
caveats the person did not ask for?

The person asked for a table to paste. Read the whole reply.

**Yes** when the reply is the table, with at most a short line or two that a person would want:
a pointer to what is still open (2.5.0's defects not triaged), or one sentence on what was left
off the card and why.

**No** when the reply wraps the table in material the person must read past: a list of what was
checked and how, PASS or UNVERIFIED markers, a count of rows and columns read, a description of
files saved, or several paragraphs of caveats.

**False pass** (reads as yes, is no):
- A short reply whose table is followed by a "Verification" heading with three bullet points of
  checks: short, but still a ledger.
- A reply that ends "Assumptions: …; Open questions: …" when nothing in the request was open.

**False fail** (reads as no, is yes):
- A reply that says in one sentence that digests and run ids were left off per the card rule.
- A reply that adds one line: "2.5.0's open defects are not counted yet, so the card says
  triage is in progress."
