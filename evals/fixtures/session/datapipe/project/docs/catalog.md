# Extract catalog

The catalog names a table, its columns and its primary key. Integer, text and real are the
supported column kinds. A table name and a column name must each be unique in its scope.
Every key column must exist. The key must not be empty.

A nullable column addition is compatible. A required column addition, a removed column,
a changed type, a nullable column made required or a changed key needs a migration decision.
The catalog comparison reports these differences. It does not apply a migration.

Read `data/catalog.json` to see the current synthetic extract definitions. These definitions
are separate from warehouse DDL. Keep a comparison result with the extract planning record.
A compatible result is evidence about the schema only. It says nothing about freshness,
row counts, permissions or available disk space.
