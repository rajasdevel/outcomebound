# Lifecycle overlay: audit

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** an auditor examines the project's controls, as for SOC 2 or ISO/IEC 27001. A solo
maintainer or a small team can face one, and many organizations face none, so it is an overlay of
its own. It goes on `solo`, `team` or `organization`, never on `prototype`.

**Fragments it would select:** none of its own.

**Scaffold set:** `+audit` adds the local lines of `templates/scaffold/audit/local.md`: the records
each control leaves, the compensating control where one person cannot be kept from approving their
own change, and the emergency path.

## Example lines

```text
Bounds: the pull request is the change record, CI the test record and the deploy log the deploy
  record.
Bounds: where one person cannot be kept from approving their own change, the compensating control
  is <the control, such as a later review of each change by a named person>, written with its risk.
Bounds: the emergency path is the normal path made fast, with its review recorded after.
```

## When to propose each line, and when to leave it out

- The records line: propose it where the auditor's evidence lives in more than one place.
- The compensating control: propose it with one maintainer, or wherever an approval can come from
  the author; the control and its risk are the person's to choose.
- Leave out any statement that the project passes an examination or holds a certificate: the
  auditor or the certification body decides that, never a file.
