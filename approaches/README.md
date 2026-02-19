# Approaches Overview

- `01_sqlite_wal_cache` (recommended): production-oriented AAOS Java implementation using SQLite/WAL architecture.
- `02_json_snapshot_cache`: Java prototype approach using full JSON snapshots.
- `03_event_log_cache`: Java alternative using append-only mutation events.

For real vehicle deployment, use `01_sqlite_wal_cache`.
