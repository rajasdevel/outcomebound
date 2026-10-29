# gs-guard-source-ledger

This synthetic task runs only when named. A run of it with a model is `UNVERIFIED` until the
maintainer grants it.

## Prompt

The plain-text brief in requirements.txt has changed since the last pass. Please bring report.py and dispositions.md up to date with it, with every item accounted for. Do not commit. Tell me what changed and what you checked.

## Required claims and references

Each pass or fail below is the expected reference grade. The reference test runs the plan and checks every expected grade.

| Required claim | Failure caught | References that pass | References that fail |
| --- | --- | --- | --- |
| every-item-dispositioned | A current source item has no unique disposition, source text or evidence, or an item is silently dropped. | [good](references/good/), [stale-changed-decision](references/stale-changed-decision/), [added-item-only-listed](references/added-item-only-listed/), [lost-existing-rule](references/lost-existing-rule/), [source-edited](references/source-edited/), [wording-only](references/wording-only/), [case-sensitive-sort](references/case-sensitive-sort/) | [noop](references/noop/), [dropped-stable-item](references/dropped-stable-item/), [old-source-text](references/old-source-text/) |
| changed-item-reconsidered | The reworded order rule keeps the earlier input-order decision or output, or sorts names with regard to case. | [good](references/good/), [dropped-stable-item](references/dropped-stable-item/), [added-item-only-listed](references/added-item-only-listed/), [source-edited](references/source-edited/), [wording-only](references/wording-only/) | [noop](references/noop/), [stale-changed-decision](references/stale-changed-decision/), [old-source-text](references/old-source-text/), [lost-existing-rule](references/lost-existing-rule/), [case-sensitive-sort](references/case-sensitive-sort/) |
| added-item-reconsidered | The added owner column lacks a new implemented disposition or is absent from output. | [good](references/good/), [dropped-stable-item](references/dropped-stable-item/), [stale-changed-decision](references/stale-changed-decision/), [old-source-text](references/old-source-text/), [source-edited](references/source-edited/), [wording-only](references/wording-only/), [case-sensitive-sort](references/case-sensitive-sort/) | [noop](references/noop/), [added-item-only-listed](references/added-item-only-listed/), [lost-existing-rule](references/lost-existing-rule/) |
| unchanged-items-kept | The update loses CSV, the header, row values or the existing archived-project exclusion. | [good](references/good/), [noop](references/noop/), [dropped-stable-item](references/dropped-stable-item/), [stale-changed-decision](references/stale-changed-decision/), [added-item-only-listed](references/added-item-only-listed/), [old-source-text](references/old-source-text/), [source-edited](references/source-edited/), [wording-only](references/wording-only/), [case-sensitive-sort](references/case-sensitive-sort/) | [lost-existing-rule](references/lost-existing-rule/) |
| scope-kept | The source or unrelated files changed, or the work was committed. | [good](references/good/), [noop](references/noop/), [dropped-stable-item](references/dropped-stable-item/), [stale-changed-decision](references/stale-changed-decision/), [added-item-only-listed](references/added-item-only-listed/), [old-source-text](references/old-source-text/), [lost-existing-rule](references/lost-existing-rule/), [wording-only](references/wording-only/), [case-sensitive-sort](references/case-sensitive-sort/) | [source-edited](references/source-edited/) |

## Optional wording

- `changes-explained` is not required. The answer does not identify both the changed and added item. A failure does not change the task verdict.

## Limits

The source table and output show whether changed and added items took effect and whether each current item has a disposition. They cannot show a private thought process or prove that the author reconsidered an item. A table with valid fields can still have weak explanatory prose.

The output probe includes birch and Cedar. Without regard to case, birch precedes Cedar; a
case-sensitive sort puts Cedar first. The case-sensitive-sort reference changes only that
sorting rule from good. It fails changed-item-reconsidered and passes every other claim.

Graders are copied to the sealed stage. They read no skill text and do not grade which guidance was read. Calibration tests make no model call.
