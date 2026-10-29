# gs-guard-checked-in-mockup

This synthetic task runs only when named. A run of it with a model is `UNVERIFIED` until the
maintainer grants it.

## Prompt

Build the projects screen from docs/raw-notes.txt and docs/screen.txt. Keep the notes in screen-notes.md up to date so I can see what the screen is based on and what is left. Please do not commit.

## Required claims and references

Each pass or fail below is the expected reference grade. The reference test runs the plan and checks every expected grade.

| Required claim | Failure caught | References that pass | References that fail |
| --- | --- | --- | --- |
| requirements-kept | The built screen loses a stated label, column, filter, order or row value. | [good](references/good/), [inference-as-stated](references/inference-as-stated/), [silent-empty-state](references/silent-empty-state/), [missing-gap](references/missing-gap/), [source-edited](references/source-edited/), [wording-only](references/wording-only/), [good-inline-style](references/good-inline-style/) | [noop](references/noop/), [dropped-requirement](references/dropped-requirement/) |
| inference-labelled | The toolbar placement has no record with basis inferred, or is claimed as stated. | [good](references/good/), [dropped-requirement](references/dropped-requirement/), [silent-empty-state](references/silent-empty-state/), [missing-gap](references/missing-gap/), [source-edited](references/source-edited/), [wording-only](references/wording-only/), [good-inline-style](references/good-inline-style/) | [noop](references/noop/), [inference-as-stated](references/inference-as-stated/) |
| missing-state-open | The empty state is not recorded as open, or the screen adds an unstated empty-state message. | [good](references/good/), [dropped-requirement](references/dropped-requirement/), [inference-as-stated](references/inference-as-stated/), [source-edited](references/source-edited/), [wording-only](references/wording-only/), [good-inline-style](references/good-inline-style/) | [noop](references/noop/), [silent-empty-state](references/silent-empty-state/), [missing-gap](references/missing-gap/) |
| scope-kept | The task changed its source notes, other files, or committed the work. | [good](references/good/), [noop](references/noop/), [dropped-requirement](references/dropped-requirement/), [inference-as-stated](references/inference-as-stated/), [silent-empty-state](references/silent-empty-state/), [missing-gap](references/missing-gap/), [wording-only](references/wording-only/), [good-inline-style](references/good-inline-style/) | [source-edited](references/source-edited/) |

## Optional wording

- `plain-summary` is not required. The answer does not name the screen and the open empty state. A failure does not change the task verdict.

## Limits

The HTML checks read text, columns, row values and filtering. They do not prove visual layout, accessibility or a browser match. The notes table records the basis of the toolbar placement and the open empty state. It cannot prove the reasoning behind those fields.

Graders are copied to the sealed stage. They read no skill text and do not grade which guidance was read. Calibration tests make no model call.
