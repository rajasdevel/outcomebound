---
id: db-migrations
family: stack
applies: schema migrations (Django, Alembic, Prisma, Flyway, Rails)
condition: when writing, applying or rolling back a schema migration
detect: ["**/migrations/*.py", "prisma/schema.prisma", "alembic.ini", "db/migrate/*.rb"]
version: 5
---
**Context** — the live schema and data volume are evidence; the ORM model is a claim about them,
not the truth.
**Bounds** — shared or production application requires its granted authority. A disposable
database that the project's own test setup creates, or a local one you create with synthetic or
fixture data, is inside scope; a copy of production or sensitive data is used only where that use
is granted, and a local copy does not remove the restrictions on that data.
**Mechanisms** — `spec` when later work relies on a semantic or backfill decision the schema cannot show; `policy-gate`
at the project's existing protected apply boundary; `broad-suite` when the changed model is used
across surfaces; `runtime-check` for actual schema, data, and service behavior after application.
**Completion bar** — exercise the forward migration and supported recovery path on a disposable
dataset within those bounds; test a backward migration when one is supported or claimed. Production
application and recovery remain unverified until observed through the project's own checks.
**Distinguish** — migration file written ≠ applied locally ≠ applied in production.
