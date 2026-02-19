# AAOS ContactsProvider Patch Plan (Pseudo-Implementation)

This document maps the reference implementation to real AOSP provider touchpoints.

Implemented Java reference code for this plan is available in:

- `src/main/java/com/autotech/aaos/contactscache/core`
- `src/main/java/com/autotech/aaos/contactscache/android`

## Candidate files to modify

- `packages/providers/ContactsProvider/src/com/android/providers/contacts/ContactsDatabaseHelper.java`
- `packages/providers/ContactsProvider/src/com/android/providers/contacts/ContactsProvider2.java`
- `packages/providers/ContactsProvider/src/com/android/providers/contacts/ContactsSyncAdapterService.java` (or AAOS-specific sync entry)
- AAOS Bluetooth/USB contact ingestion component (product-specific path)

## Schema additions (ContactsDatabaseHelper)

```sql
CREATE TABLE synced_contacts_cache (
    source_device TEXT NOT NULL,
    external_contact_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    phones_json TEXT NOT NULL,
    emails_json TEXT NOT NULL,
    avatar_etag TEXT,
    source_version INTEGER NOT NULL,
    source_last_modified_ms INTEGER NOT NULL,
    local_updated_ms INTEGER NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(source_device, external_contact_id)
);

CREATE INDEX idx_synced_cache_source_deleted_name
ON synced_contacts_cache(source_device, deleted, display_name);
```

## Provider URI and query surface

Add internal URI for cached contacts:

- `content://com.android.contacts/synced_cache`

Enforce stricter access checks than generic contacts URIs:

- system/signature UID only for write
- read restricted to approved callers

## Sync flow pseudo-code

```java
public SyncSummary applyFullSync(String sourceDevice, List<SyncContact> incoming, String token) {
    db.beginTransaction();
    try {
        SyncSummary summary = new SyncSummary();
        Set<String> seenIds = new HashSet<>();

        for (SyncContact c : dedupeByIdKeepLatest(incoming)) {
            UpsertResult result = upsertContact(db, sourceDevice, c);
            summary.bump(result);
            seenIds.add(c.externalId);
        }

        int deleted = markMissingAsDeleted(db, sourceDevice, seenIds);
        summary.deleted += deleted;
        upsertSyncState(db, sourceDevice, token, nowMs());

        db.setTransactionSuccessful();
        return summary;
    } finally {
        db.endTransaction();
    }
}
```

## Migration strategy in provider upgrade

1. Bump DB version in `ContactsDatabaseHelper`.
2. Create new cache tables/indexes in `onUpgrade`.
3. Initialize sync state rows lazily on first sync.
4. Trigger scheduled full sync for each paired phone source.

## Permissions and privacy controls

- Validate Binder calling UID before read/write.
- Keep cache tables inaccessible via exported broad URIs.
- Strip or hash PII in logs.
- Rely on encrypted userdata partition (FBE).

## Performance knobs

- WAL mode enabled for provider DB.
- Batching writes within single transaction.
- Temporary table strategy for full-sync diff instead of large `IN (...)` lists.
