# Production Deployment Guide (AAOS)

This guide maps the Java implementation in this folder to production deployment inside an AAOS stack.

## 1) Integration target

Recommended integration point is the Contacts provider/service layer in AOSP:

- `core` package (`com.autotech.aaos.contactscache.core`) -> shared business logic
- `android` package (`com.autotech.aaos.contactscache.android`) -> SQLite persistence implementation

Keep business logic separated from Android APIs for maximal unit-test coverage.

## 2) Required provider-level controls

1. Restrict cache URI access by UID and permission.
2. Enforce signature/system-only writes for sync services.
3. Gate non-system reads to minimum allowed fields.
4. Redact PII in logs/metrics.

Use `ContactsCacheAccessEnforcer` pattern at every binder entrypoint.

## 3) Sync pipeline rules for correctness

1. Always pass monotonic `sourceSyncSequence` from source adapter.
2. Reject sequence regressions unless explicit recovery flow is active.
3. Mark missing rows deleted only for full snapshots marked complete.
4. Use delta sync for routine updates and explicit deletion IDs.
5. Persist sync state token/sequence every successful transaction.

## 4) Edge cases handled in code

- duplicate contact IDs in same sync payload
- stale source version updates
- source sync sequence regression
- conflicting delta payload (same ID in upsert and delete)
- partial snapshots that should not trigger mass deletion
- invalid/blank IDs dropped
- normalization of phone/email/name payloads
- per-device isolation for multi-phone pairing
- configured limits to prevent runaway memory/storage usage

## 5) Data retention

- Soft delete rows first (`deleted = 1`).
- Purge tombstones asynchronously by retention window (for example, 14-30 days).
- Record purge metrics to monitor DB growth.

## 6) Performance settings

- Enable WAL mode.
- Use one DB transaction per sync batch.
- Keep `(source_device, deleted, display_name)` index.
- Keep `(source_device, local_updated_ms)` index for purge scans.
- Limit UI query page sizes.

## 7) Migration strategy

1. Add schema in provider DB upgrade path.
2. Initialize sync state lazily.
3. Trigger per-device full sync after upgrade.
4. Keep fallback path for one release if migration fails.

## 8) Security and privacy

- Rely on FBE-backed userdata at rest.
- Keep raw phone/email out of telemetry.
- Provide optional stronger at-rest crypto if OEM policy requires.
- Clear data on profile/user reset and unpair flow.

## 9) Validation gates before vehicle rollout

1. Unit tests for sync engine (included).
2. Integration tests for real SQLite store on target build (see `instrumentation-tests`).
3. Reboot persistence validation.
4. Disconnect/reconnect race validation.
5. Upgrade migration and rollback validation.
6. Cold boot and large phonebook performance benchmarks.

## 10) Operational metrics to ship

- sync duration (p50/p95)
- inserted/updated/deleted/stale counts
- cache query latency
- cache hit ratio on cold boot
- migration success/failure count
- DB size over time
