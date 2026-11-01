# Recovery and replay

Checkpoint storage records an offset and generation per source. An advance names the
observed generation, cannot lower the offset and uses atomic file replacement. This local
store has one writer; it does not coordinate machines.

The current replay helper divides a requested interval into hourly windows. Membership
includes both ends. The caller reports the highest observed source offset plus one. It
performs no load or checkpoint write. See docs/replay-api.md for the current interface.

Archive restore uses the catalog and the CSV inspector before the loader. The loader types
integer columns before insertion. Generation checks and archive retention are separate.
The local unit modules cover these paths; the SQL integration suite covers the scheduler.
