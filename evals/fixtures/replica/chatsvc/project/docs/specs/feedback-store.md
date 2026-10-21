# Spec: feedback store

Status: accepted (2026-09).

## Requirements

1. One submission is one JSON object on one line of the store, appended, never rewritten.
2. A submission names its conversation, the release that answered and a rating, `up` or `down`;
   anything else is refused with 400.
3. Triage sets `label` afterwards, in the store's daily export; the service writes `null`.
4. Counting: the latest submission of a conversation is the one that counts
   ([feedback](../feedback.md)). Reports of issues count conversations, not submissions.
5. Releases compare numerically (1.10.0 is after 1.9.0).

## Not in scope

Deleting a submission (a privacy request goes through the data team's own process).
