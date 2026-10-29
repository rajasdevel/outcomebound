# Portable bundles

Use python3 -m tally.bundles build FILE --out DIR, verify DIR, or diff OLD NEW.
A bundle holds canonical entries.csv, summary.json and manifest.json with SHA-256 digests.
Existing destinations and mixed grouping refuse with E104. Invalid content refuses with E102.
Publication uses a rename on one local filesystem; it does not reserve names against another writer.
Integrity detects changed bytes; it does not establish authenticity. No signature is supplied.
