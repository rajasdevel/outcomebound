---
id: db-migrations
family: stack
applies: schema migrations (Django, Alembic, Prisma, Flyway, Rails)
condition: when writing, applying or rolling back a schema migration
detect: ["**/migrations/*.py", "prisma/schema.prisma", "alembic.ini", "db/migrate/*.rb"]
version: 6
---
**Context** — the live schema and data volume are evidence; the ORM model is a claim about them,
not the truth. During the transition old and new application versions run at once, and every live
version must tolerate the schema and data state at each step: no one order fits every change (a
column the new code reads must exist before it ships; a drop or rename breaks the old code).
**Bounds** — shared or production application requires its granted authority, and a brief that asks
for it states the order and the recovery (`deploy` fragment). Contraction (a drop, a rename, a
tighter constraint) waits until no consumer, version, job or report needs the old form. A disposable
database that the project's own test setup creates, or a local one you create on the server that
setup already uses, with synthetic or fixture data, is inside scope; a copy of production or sensitive data is used only where that use
is granted, and a local copy does not remove the restrictions on that data.
**Mechanisms** — `spec` when later work relies on a semantic or backfill decision the schema cannot show; `policy-gate`
at the project's existing protected apply boundary; `broad-suite` when the changed model is used
across surfaces; `runtime-check` for actual schema, data, and service behavior after application.
**Completion bar** — exercise the forward migration and supported recovery path on a disposable
dataset within those bounds; test a backward migration when one is supported or claimed. Production
application and recovery remain unverified until observed through the project's own checks.
**Distinguish** — migration file written ≠ applied locally ≠ applied in production; code rolled
back ≠ data recovered, since a down migration restores the shape, not what was written meanwhile.
