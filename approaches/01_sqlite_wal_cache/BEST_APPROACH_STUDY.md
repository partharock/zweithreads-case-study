# Detailed Study: Recommended Approach for Persistent Synced Contacts in AAOS

## 1. Context and problem framing

In current behavior, synced contacts from Bluetooth/USB are memory-resident only. This causes:

- cold-start resync delays after head unit reboot,
- user-visible data loss during temporary phone disconnects,
- repeated sync traffic and avoidable battery usage.

For an automotive infotainment system, this is especially problematic because contact search and call handoff are high-frequency flows expected to be instant.

## 2. Why SQLite + WAL + sync metadata is the best approach

Compared to file snapshots or append-only logs, a provider-style SQLite cache gives the strongest balance across reliability, query speed, migration safety, and debuggability.

### Strengths

- Native fit with ContactsProvider internals and Android provider architecture.
- Reliable persistence with transactional semantics.
- Efficient indexed reads for search/autocomplete and favorites views.
- Easy conflict handling via `source_version` and `source_last_modified_ms`.
- Natural support for schema migrations through `user_version` and helper upgrades.

### Tradeoff

- More schema design and migration work than a naive JSON dump.

That tradeoff is acceptable in AAOS because persistent contact reliability is platform-critical and long-lived.

## 3. Reference architecture

- **Source adapters**: Bluetooth PBAP / USB sync agents emit normalized contact payloads.
- **Sync engine**: resolves full-sync and delta-sync inputs into deterministic DB operations.
- **Persistent cache store**: SQLite tables for contacts + sync state.
- **Read APIs**: provider queries return active (non-deleted) contacts with index-backed filters.
- **Retention worker**: purges soft-deleted rows beyond retention window.

## 4. Data model decisions

### Contacts cache table

Key fields:

- `source_device`: source namespace (`deviceAddress`/`account` partition).
- `external_contact_id`: stable ID from source phone.
- `display_name`, `phones_json`, `emails_json`, `avatar_etag`.
- `source_version`: monotonic change version from source.
- `source_last_modified_ms`: source-side last modified timestamp.
- `local_updated_ms`: local mutation time for purge/telemetry.
- `deleted`: soft-delete flag.

Primary key:

- `(source_device, external_contact_id)` to avoid collisions across multiple paired phones.

Indexes:

- `(source_device, deleted, display_name)` for UI query speed.
- `(source_device, local_updated_ms)` for retention jobs.

### Sync state table

Per source-device metadata:

- `last_full_sync_ms`
- `last_sync_token`
- `cache_schema_version`

This supports token-based incremental sync and diagnostics.

## 5. Synchronization model

### Full sync

1. Deduplicate incoming records by `external_contact_id` (keep newest version).
2. Upsert each contact.
3. Mark local contacts missing from incoming set as soft-deleted.
4. Update sync state token/time.

### Delta sync

1. Upsert incoming changed/new contacts.
2. Soft-delete explicit deletion IDs.
3. Update sync state token/time.

### Conflict rule

- `source_version` is authoritative.
- Incoming rows with lower version are ignored (`stale_ignored`).
- Same version but payload difference is accepted only when source timestamp indicates same/newer state.

## 6. Migration plan for existing users

### Migration trigger

Run on first boot with upgraded provider schema.

### Steps

1. Create new cache tables and indexes.
2. If old transient cache has recoverable local source (rare), backfill once.
3. Initialize `sync_state` for each paired source with `last_sync_token = NULL`.
4. Schedule one full sync per source in low-priority job queue.
5. Serve reads from persistent cache immediately after first source sync succeeds.

### Compatibility behavior

- If migration fails, fallback to legacy in-memory flow and retry migration next boot.
- All migration operations are wrapped in a single DB transaction.

## 7. Performance strategy

### Cold start

- Read directly from persistent DB; no mandatory online sync.
- Use capped read windows (`LIMIT`) for initial lists.

### Write performance

- WAL mode for concurrent reads while sync writes run.
- Batch upserts inside one transaction.
- Avoid large `IN` clauses by using temp tables for full-sync diff.

### Scale expectations

For 10k-30k contacts:

- indexed prefix searches remain interactive,
- full-sync diff remains manageable using temp-ID table pattern,
- delta sync cost is near O(changes), not O(total contacts).

## 8. Security and privacy

### At-rest protection

- Use file-based encryption (FBE) on Android userdata partition.
- Optionally protect high-risk fields with SQLCipher/device-keystore keys in product variants needing stronger policy.

### Access control

- Provider permission gates (`READ_CONTACTS` + signature/system checks for system components).
- Enforce calling UID validation for internal cache URIs.
- Expose only minimal fields to non-system callers.

### Privacy-safe observability

- Redact PII in logs.
- Emit aggregate counters only (inserted/updated/deleted/stale).
- No raw phone/email in telemetry.

## 9. Reliability and failure handling

- Transaction-wrapped sync operations prevent partial writes.
- Soft-delete avoids accidental hard-loss on transient source glitches.
- Periodic purge of old deleted rows controls DB growth.
- Corruption path: provider detects and rebuilds cache via full sync.

## 10. Test strategy

### Unit tests

- restart persistence
- full-sync missing-row deletion
- stale update rejection
- delta update + delete
- duplicate ID dedupe behavior

### Integration tests (AAOS target)

- reboot persistence checks
- multi-device pairing isolation
- connection-loss recovery
- upgrade migration from older provider DB

## 11. Rollout plan

1. Land schema and sync engine behind feature flag.
2. Dogfood in internal vehicle builds with telemetry.
3. Validate migration timing on low-end hardware.
4. Enable by default and retain fallback for one release cycle.

## 12. Why this is a good fit for your background

Given your Samsung app background (Settings, Notification, Wallpaper), this approach is aligned with system-app engineering patterns you already use:

- content provider contracts,
- robust lifecycle handling,
- defensive migration/upgrade logic,
- privacy-first data handling.

The new domain-specific learning is mostly in source sync protocols (PBAP/USB contact feed semantics), not in fundamental persistence architecture.
