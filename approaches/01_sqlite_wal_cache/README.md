# Approach 1 (Recommended): AAOS SQLite WAL Persistent Cache (Java)

This is the production-target approach for AAOS ContactsProvider integrations.

## What is included

- Production-grade **core sync engine** in Java:
  - transactional sync application
  - stale-version protection
  - sync-sequence regression rejection
  - full-snapshot vs partial-snapshot safety
  - input normalization and dedupe
  - per-device isolation and quota limits

- **AAOS Android integration layer** in Java:
  - `SQLiteOpenHelper` schema with WAL
  - SQLite-backed store implementation
  - binder UID access enforcement helper

- Runnable **JVM tests** (no Android SDK dependency) for core logic.

## Source layout

- `src/main/java/com/autotech/aaos/contactscache/core` - domain, store contracts, sync engine.
- `src/main/java/com/autotech/aaos/contactscache/inmemory` - in-memory transactional store for tests.
- `src/main/java/com/autotech/aaos/contactscache/android` - Android SQLite implementation for AAOS integration.
- `src/test/java/com/autotech/aaos/contactscache/core` - edge-case test runner.
- `instrumentation-tests` - Android runtime integration tests + AOSP files (`Android.bp`, `AndroidTest.xml`, templates).
- `PRODUCTION_DEPLOYMENT_GUIDE.md` - rollout checklist and production hardening guidance.

## Run JVM tests

```bash
./approaches/01_sqlite_wal_cache/run_jvm_tests.sh
```

## Run complete validation

```bash
./approaches/01_sqlite_wal_cache/run_all_checks.sh
```

- Runs JVM core tests.
- Runs Android source compile check against `android.jar`.
- Skips connected instrumentation tests by default.

To include connected instrumentation tests:

```bash
RUN_CONNECTED_TESTS=1 ./approaches/01_sqlite_wal_cache/run_all_checks.sh
```

## Notes for AAOS deployment

- Deploy `android` package classes into your AOSP/AAOS module (`ContactsProvider` integration path).
- Keep `core` package as shared business logic to maximize unit-test coverage.
- Use strict caller UID checks in provider entrypoints before exposing cache URIs.
- Use `instrumentation-tests` as the baseline for device-level CI coverage.
