# Carry an outcome through its lifecycle

Use this reference to settle a change of delivery route or exposure, or a delivery stage whose
inputs, owner or authority are unsettled; continuing an accepted task on its route needs none of it.
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
("Streams — <stream>: route in <file>; takes <kind of change>", with an optional
"; fragments <id>, <id>" naming the fragments that apply to that stream only), the gates ("Gates —"), the
exposure ("Exposure —") and the measure of a better outcome ("Better means —"). A route
document a "Streams —" line names must be one the next person can open: committed, or named as
private with who holds it; a pointer to an ignored or private file says so instead of dangling.
Choose the stream that takes your change, read its route in the project's own document, and
follow that route; the
table below fills only what the route is silent on. A person decides only at an irreversible edge,
an outside contract or an unsettled intent; every other choice on the route is yours. A gate a "Gates —" line names is its owner's to pass.

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
| Maintenance to retirement | Find remaining consumers, data and compatibility obligations, retention requirements, and recovery needs. Complete authorized preparation; verify the removal and remaining consumers after an authorized cutover. Once the removal is authorized, add an entry to `.outcomebound/retired.json` for each path, command or process step it drops. | Nothing is being removed and no end-of-life obligation is in scope. |

A retired term, path, command or process step gets an entry in the project's
`.outcomebound/retired.json` in the change that retires it, so that a copy left in a guide fails
`instructions check`; `$(outcomebound home)/schemas/retired-terms.schema.json` gives the form. This
includes a step dropped from the project's own route document, outside any transition. Where a
floor is installed with no `docs.retired` claim, the change that adds the first entry adds that
claim; `outcomebound floor propose` prints it.

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
- a signal named in a "Leave when —" line appears; the line's right side is the brief to open.

A drift line from `adopt --check` (a file shows a signal that the record contradicts) is not a
transition of its own: check it against the "Leave when —" rows and the person's own words. A line
about recent authors can be a contributor, not a maintainer, or one person under two identities
that share neither name nor email (a `.mailmap` joins them); ask before treating it as a second
maintainer. Where the person settles it, a "Drift — <signal>: <reason>" line in the local
fragment's Bounds slot, on a line of its own with a reason, marks it settled; the line still
prints beside the current evidence, so a settlement that no longer fits is seen. Do not raise a
settled line again unless the evidence now differs from the reason given.

Nothing switches on its own. A directive that names the new route completely, the route (a
lifecycle template or the fragment set) and the exposure, is the decision: write the "Changed —"
line with the person's words in quotes, run the inventory below, apply what the directive
settles, and write a brief (the `decision-brief` skill) only for what it leaves open; where
nothing is open, write none. A directive that names only an exposure fact (a first outside user, a
second maintainer, a client contract) is partial: the inventory runs, the brief asks for the
route, and the line is written when the brief is answered. Otherwise the brief asks for the
decision. The inventory's main value is the work in flight and what each item now owes, so it runs
even when no fragment changes. Until the route is decided, the inventory and the brief are the
only writes: each record of the work in flight (a brief, a grant, a ticket, a branch) stays as it
is, and what it now owes goes in the inventory. It holds:

- the fragment diff: which fragments turn on and which turn off, which may be none when only the
  route changes, as with the person's directive;
- the work in flight: open tickets from the ticket export, branches with commits the main line
  does not hold and their open requests, worktrees with uncommitted work, open briefs, standing
  grants with their dates, a release artifact not yet published, and a deploy or cutover receipt in
  a partial phase. Look where the project keeps them: the ticket export, `git branch` and
  `git worktree list`, the goal envelope, `.agents/work/` where the `workspace` fragment applies,
  and the grants file the project names. What you cannot read, such as a hosted request list, is
  `UNVERIFIED`;
- what each item now owes under the new route;
- what the change invalidates;
- what still holds under a lighter route: data kept, versions supported, consumers served and
  contract duties, each with its owner or its retirement;
- what to retire: the entries the change adds to `.outcomebound/retired.json`. Once decided, write
  them in the commit that adds the "Changed —" line, and quote the old term in that line, so the
  line does not count.

Between the scaffold's lifecycles, run `outcomebound scaffold . --lifecycle <new> --from <old>`,
which writes nothing, and put its plan in the inventory: its `write` lines and the platform acts
the move adds; each `not required` line goes to what still holds or to what to retire, as it says; the replaced local lines
and the fragments no longer selected go in the fragment diff. Once the route is decided, `--accept`
writes the absent files, and you add the printed blocks.

After a complete directive or the person's answer to the brief, add a dated line to the local
fragment's Context, in this form, with the person's words and each old term in double quotes:

Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired
"<old term>"; invalidated <what no longer holds>.

Keep one line for each stream: it replaces that stream's older line, which Git keeps. Where adoption refuses the change, the line reads "approved, not applied", and
the old selection stays active until the check that refused passes. Plan the stages
not yet reached again, and plan again each finished stage whose evidence the change invalidates: it
keeps its dated result as history, reads `UNVERIFIED` for the new exposure, and gets its own
corrective item. Each item in flight keeps the state its own record shows; do not mark it done or
undone to suit the new route. A move back to a lighter lifecycle is a normal transition, not a
failure.

At each handoff, check the "Leave when —" lines against what you can observe. When the route does
not fit the work, such as process that outweighs the change, a gate with no owner, or a stalled
lane, report the misfit as a brief judged against the "Better means —" line. Do not edit the route
or the fragments yourself. A resume that finds worktrees with uncommitted work and nothing landed
since the last handoff reports that inventory and asks whether the pause is deliberate, with the
default it takes; the work it can do under its grant goes on.
