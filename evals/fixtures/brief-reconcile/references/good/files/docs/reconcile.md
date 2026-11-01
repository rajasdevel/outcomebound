# Versioned reconciliation

Use python3 -m datapipe.reconcile plan INPUT --db FILE, apply INPUT --db FILE, or inspect --db FILE.
Plan is read-only. Apply uses one SQLite transaction with BEGIN IMMEDIATE.
The items table holds current versions; history records each key and version and its payload.
An exact historical repeat is duplicate. An unseen older version is stale. Tombstones retain versions.
Conflicting historical payloads refuse the whole batch. Correct the input and retry after a refusal.
SQLite supplies transaction durability on the local filesystem. No service or migration is added.
