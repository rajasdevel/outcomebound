# Extract manifests

Version 1 records orders or events, relative file names, declared row counts and SHA256.
The parser checks lexical paths, known tables and checksum shape. It does not inspect file
content. The CSV inspector checks individual headers, cell types and literal row keys.
The loader types integer columns before insertion into the warehouse. Count reconciliation
compares expected raw table counts after loading. Checkpoints advance separately.

More than one extract can supply the same table. The existing total_rows helper sums their
counts. A schema comparison reports compatibility changes without applying a migration.
