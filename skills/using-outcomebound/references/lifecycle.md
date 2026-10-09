# Carry an outcome through its lifecycle

Use this reference when work crosses stages or an apparent delivery leaves the outcome unmet.
Start at the project's current state. A local correction can go straight to its relevant check;
stage names do not require new specs, tickets, approvals, services or documents.

At a handoff, carry the outcome, current evidence, bounds and completion bar into the record the
project already uses. Include the input the next action needs, its expected result, who takes
it and any remaining authority limit. A role named in a plan is not that person's acceptance.
If no next owner is established, report that gap; do not claim an operational handover is done.

## Select the applicable transition

The skills named here are the installed working skills. Project instructions supply the actual
commands, delivery route and gates. This reference needs no optional fragment or engine command.

Where the project's `local` fragment names its route, work inside it. It holds the streams
("Streams — <stream>: route in <file>; takes <kind of change>"), the gates ("Gates —"), the
exposure ("Exposure —") and the measure of a better outcome ("Better means —"). A route
document a "Streams —" line names must be one the next person can open: committed, or named as
private with who holds it; a pointer to an ignored or private file says so instead of dangling.
Choose the stream that takes your change, read its route in the project's own document, and
follow that route; the
table below fills only what the route is silent on. A person decides only at an irreversible edge,
an outside contract or an unsettled intent; every other choice on the route is yours.

| From and to | Carry forward and check | When the extra stage adds no work |
| --- | --- | --- |
| Idea to requirements | Use `gather-requirements` where the outcome is unclear or comes from sources; use `sync-tracker` to read a tracker that is not the ticket store into a source. Keep user constraints, corrections, assumptions and unresolved choices attached to the requirements. For an idea with no repository yet, follow [the new-project reference](new-project.md) to a walking skeleton first. | The request and its completion bar are already clear; no source constraints need reconciliation. |
| Requirements to design | Settle choices that later work cannot recover from the code. Use `explain-spec` when a person must act on a design they did not write. | A routine change leaves no decision that later work depends on; explanation is not needed merely because a spec exists. |
| Design to accepted work | Use `slice-tickets` if separate outcomes need tracking or delegation. Preserve requirement coverage and acceptance; an id mapping alone does not show that a requirement is met. | One bounded task can be completed directly under the current grant. |
| Accepted work to implementation | Use `hand-off-tickets` for a receiving implementer. Give current inputs, owned scope, checks and authority, sized to that implementer. | The current worker can proceed from the accepted task without a new package. |
| Implementation to validation | Use `tests-worth-keeping` for checks of the changed risk and `diagnose` for an unknown cause. Check the user-visible path where the outcome depends on it. Identify the revision, environment and result; a missing tool is not a pass. | Existing evidence still covers unchanged inputs; skip redundant checks, not the project's required checks. |
| Validation to review and landing | Resolve required findings with `review-findings`; use the project's landing route and checks for the revision that will land. Where the change goes to landing as a request with a fix loop, use `land-change`. Keep outstanding findings and unavailable evidence visible. | No review is required and no uncaught material risk calls for it. A local task may need no remote landing. |
| Delivery to acceptance by an outside party | Where a client or a regulator accepts the work, use `run-acceptance` and the project's `client` fragment. Name the build and the person who accepts; your own pre-run is not their acceptance, and only an accepted build is promoted. | Nobody outside the project accepts the work. |
| Landing to release and deployment | Identify the artifact, destination, expected observation and recovery action. Verify identity and behavior at the requested destination under its actual grant and gate. | The outcome ends at a checked local artifact or landing; publication and deployment have no role in it. |
| Delivery to operation | Establish the next owner, finite observation window, success or failure signals, response route and recovery bounds. Check the delivered version and its relevant user path. | No service or ongoing obligation is created or changed; existing operational coverage still fits. |
| Incident or feedback to maintenance | Stabilize within the grant, retain relevant evidence, then use `diagnose` for an unknown cause. Return a changed need to requirements, or a defect to a bounded repair and its recurrence check. | No incident, defect, changed need or maintenance obligation calls for work. |
| Maintenance to retirement | Find remaining consumers, data and compatibility obligations, retention requirements, and recovery needs. Complete authorized preparation; verify the removal and remaining consumers after an authorized cutover. | Nothing is being removed and no end-of-life obligation is in scope. |

## Select quality dimensions from the changed risk

Include a dimension in the completion bar when its failure would defeat the outcome. Use the
project's existing specialist guidance and checks when available.

- Access, secrets, untrusted input or changed trust boundaries call for security checks.
- Personal or sensitive data calls for checks of use, exposure, access and retention.
- Changed user interaction calls for accessibility checks for the users and input methods it serves.
- Shared interfaces, stored data or supported environments call for compatibility and migration checks.
- Service behavior or resource demand calls for reliability, capacity and performance evidence.
- A state change that is hard to undo calls for recovery evidence, including whether a backup
  can be restored when the completion bar depends on restoration.

A passing quality floor covers its configured checks. It does not establish every applicable
quality dimension. Add a missing check where that risk warrants it; do not add a specialist
workflow merely because its name appears here.

## Keep delivery and ongoing work bounded

Built, published, deployed and observed are separate states. A passing build cannot settle a
runtime claim. For an operational observation, record what was visible during the agreed window
and what was unavailable. Missing telemetry leaves the affected claim UNVERIFIED; it is not zero
failures. Correct a known failure or route it to the named owner instead of calling delivery done.

An observation window is not a grant to start a persistent monitor or an unattended job. Use an
existing authorized service where it fits. A new ongoing job needs its scope, owner and stop
condition covered by the grant. At the end of the bounded work, hand over the remaining actions
and their evidence instead of silently extending the run.

For retirement, a plan to delete is not evidence that consumers have migrated or retention has
ended. Check those conditions before removal. A restore command alone does not prove recovery.
Use `decision-brief` for an act that expands authority or crosses an ungranted irreversible edge;
hold that act and continue independent authorized work. Keep remaining users and obligations
visible until their completion is observed.

## When the project's exposure or route changes

A change of lifecycle is a change of exposure or of route. It is a transition when:

- a fact of the "Exposure —" line moves: who can be hurt, who accepts the work, which acts cannot
  be undone, the expected life, who maintains it, or how much agents write against review capacity;
- the person gives a directive that changes the route or the exposure;
- a stream starts or ends;
- the authority model changes;
- a signal named in a "Leave when —" line appears; the line's right side is the brief to open;
- a session resumes and finds work that never landed: worktrees with uncommitted work, none ahead
  of the main line, no recent commit;
- `adopt --check` prints a drift line: a file shows a signal that the record contradicts.

Nothing switches without the person. Write one decision brief (the `decision-brief` skill). Its
main value is the inventory of work in flight and what each item now owes, so it is written even
when no fragment changes. For a resume, it asks first whether the pause is deliberate, before any
lane restarts. It holds:

- the fragment diff: which fragments turn on and which turn off, which may be none when only the
  route changes, as with the person's directive;
- the work in flight: open tickets from the ticket export, worktrees with uncommitted work, open
  briefs, standing grants with their dates, and a deploy or cutover receipt in a partial phase;
- what each item now owes under the new route;
- what the change invalidates;
- what to retire.

On a yes, add a dated line to the local fragment's Context: "Changed — <date>: <what>, decided by
<who>, invalidated <what>". Plan again only the stages not yet reached. Each item in flight keeps
the state its own record shows; do not mark it done or undone to suit the new route. A move back to
a lighter lifecycle is a normal transition, not a failure.

At each handoff, check the "Leave when —" lines against what you can observe. When the route does
not fit the work, such as process that outweighs the change, a gate with no owner, or a stalled
lane, report the misfit as a brief judged against the "Better means —" line. Do not edit the route
or the fragments yourself.
