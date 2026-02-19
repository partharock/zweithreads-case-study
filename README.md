# zweithreads-case-study

AAOS infotainment case study repository for **persistent synced contacts cache** design and implementation.

## Repository structure

- `docs/AAOS_Persistent_Contacts_Case_Study.md` - full technical report.
- `docs/AAOS_Persistent_Contacts_Case_Study.docx` - Word report deliverable.
- `approaches/01_sqlite_wal_cache` - recommended AAOS Java implementation.
- `approaches/02_json_snapshot_cache` - JSON snapshot alternative.
- `approaches/03_event_log_cache` - append-only event log alternative.

## Run recommended approach tests

```bash
./approaches/01_sqlite_wal_cache/run_jvm_tests.sh
```

## Android Integration Tests

- Instrumentation test scaffold:
  - `approaches/01_sqlite_wal_cache/instrumentation-tests`

## Notes

- The recommended implementation is split into:
  - `core` (testable sync/cache logic)
  - `android` (AAOS SQLite integration classes)
- Android classes are intended to be integrated into your ContactsProvider/service module in AOSP.
