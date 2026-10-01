---
id: db-migrations
family: stack
applies: schema migrations (Django, Alembic, Prisma, Flyway, Rails)
condition: when writing, applying or rolling back a schema migration
detect: ["**/migrations/*.py", "prisma/schema.prisma", "alembic.ini", "db/migrate/*.rb"]
version: 4
---
**Context** — the live schema and data volume are evidence; the ORM model is a claim about them,
not the truth.
**Bounds** — shared or production application requires its granted authority. A disposable
database is inside scope only when its creation and dataset are authorized; a local copy does
not remove restrictions on production or sensitive data.
**Mechanisms** — `spec` when later work relies on a semantic or backfill decision the schema cannot show; `policy-gate`
at the project's existing protected apply boundary; `broad-suite` when the changed model is used
across surfaces; `runtime-check` for actual schema, data, and service behavior after application.
**Completion bar** — exercise the forward migration and supported recovery path on an authorized
disposable dataset; test a backward migration when one is supported or claimed. Production
application and recovery remain unverified until observed through the project's own checks.
**Distinguish** — migration file written ≠ applied locally ≠ applied in production.
