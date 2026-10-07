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

| From and to | Carry forward and check | When the extra stage adds no work |
| --- | --- | --- |
| Idea to requirements | Use `gather-requirements` where the outcome is unclear or comes from sources. Keep user constraints, corrections, assumptions and unresolved choices attached to the requirements. | The request and its completion bar are already clear; no source constraints need reconciliation. |
| Requirements to design | Settle choices that later work cannot recover from the code. Use `explain-spec` when a person must act on a design they did not write. | A routine change leaves no decision that later work depends on; explanation is not needed merely because a spec exists. |
| Design to accepted work | Use `slice-tickets` if separate outcomes need tracking or delegation. Preserve requirement coverage and acceptance; an id mapping alone does not show that a requirement is met. | One bounded task can be completed directly under the current grant. |
| Accepted work to implementation | Use `hand-off-tickets` for a receiving implementer. Give current inputs, owned scope, checks and authority, sized to that implementer. | The current worker can proceed from the accepted task without a new package. |
| Implementation to validation | Use `tests-worth-keeping` for checks of the changed risk and `diagnose` for an unknown cause. Check the user-visible path where the outcome depends on it. Identify the revision, environment and result; a missing tool is not a pass. | Existing evidence still covers unchanged inputs; skip redundant checks, not the project's required checks. |
| Validation to review and landing | Resolve required findings with `review-findings`; use the project's landing route and checks for the revision that will land. Keep outstanding findings and unavailable evidence visible. | No review is required and no uncaught material risk calls for it. A local task may need no remote landing. |
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
