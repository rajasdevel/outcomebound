# Preflight contract

`datapipe.manifests.preflight(document, root, catalog)` is the read-only entry point.
The catalog is a dictionary of `datapipe.catalog.Table` values. Parse the complete manifest
before opening a file. Then use the catalog and `extract_io` to inspect every file. Reject
missing catalog tables, missing files, header differences, bad cell types, duplicate row
keys, row-count differences and checksum differences. Reject symbolic links that escape
the root. Two names that resolve to one file are duplicates, even across tables.

Return `{"files": 2, "rows": {"orders": 3}}` for two valid files with one and two orders.
Return `{"files": 0, "rows": {}}` for an empty manifest. Preserve input order during
inspection. Every refusal is a `ValueError`. Do not write a warehouse, checkpoint or file.
Use the existing parser, catalog and inspector. There is no new loader or service to build.

The feeds under `docs/feeds/` explain where schemas and recovery requirements differ. Their
JSON contracts and generated tests are examples to inspect, not production configuration.
CSV inspection and catalog comparison have separate unit modules.
