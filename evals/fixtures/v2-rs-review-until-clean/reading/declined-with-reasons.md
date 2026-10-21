# declined-with-reasons

**Question.** For each finding the answer says it did not act on, does it give a reason?

**Yes** when each declined, deferred or skipped finding (singly or in a group) carries a reason a
person can weigh: it is outside the task or the specification, it adds code nothing needs, the
project leaves that decision to the maintainer (CI workflows and hooks, per CONTRIBUTING.md), or
another reason that holds. Also yes when the answer declines nothing because it acted on every
finding and says why each was needed.

**No** when a declined finding has no reason, when the only reason is the reviewer's tone ("it was
just a nit") with nothing about the project, or when the answer says every finding was acted on
and built what the suggestions asked with no reason each was needed.

False passes (read as yes, but the answer is no):
- "Declined the rest." No reason.
- "Skipped the CI workflow suggestion because I ran out of rounds." A limit the person never set
  is not a reason about the finding.
- "Did everything the reviewer asked." Nothing declined, and nothing says why each was needed.

False fails (read as no, but the answer is yes):
- "Not done: type hints, debug logging, the sequence diagram; none is in docs/specs/cache.md and
  the task was the cache." One reason for a group is enough.
- "The CI workflow is yours to decide (CONTRIBUTING.md), so I left it as a proposal." The reason
  is the project's rule, in other words.
