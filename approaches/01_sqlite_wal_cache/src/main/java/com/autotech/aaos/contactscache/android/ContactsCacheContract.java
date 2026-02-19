package com.autotech.aaos.contactscache.android;

public final class ContactsCacheContract {
    public static final String DB_NAME = "synced_contacts_cache.db";
    public static final int DB_VERSION = 2;

    public static final String TABLE_CONTACTS = "synced_contacts_cache";
    public static final String TABLE_SYNC_STATE = "synced_contacts_sync_state";

    public static final String COL_SOURCE_DEVICE = "source_device";
    public static final String COL_EXTERNAL_CONTACT_ID = "external_contact_id";
    public static final String COL_DISPLAY_NAME = "display_name";
    public static final String COL_PHONES_JSON = "phones_json";
    public static final String COL_EMAILS_JSON = "emails_json";
    public static final String COL_AVATAR_ETAG = "avatar_etag";
    public static final String COL_SOURCE_VERSION = "source_version";
    public static final String COL_SOURCE_LAST_MODIFIED_MS = "source_last_modified_ms";
    public static final String COL_LOCAL_UPDATED_MS = "local_updated_ms";
    public static final String COL_DELETED = "deleted";

    public static final String COL_LAST_FULL_SYNC_MS = "last_full_sync_ms";
    public static final String COL_LAST_SYNC_TOKEN = "last_sync_token";
    public static final String COL_LAST_SOURCE_SYNC_SEQUENCE = "last_source_sync_sequence";
    public static final String COL_CACHE_SCHEMA_VERSION = "cache_schema_version";

    public static final String INDEX_SOURCE_DELETED_NAME = "idx_synced_cache_source_deleted_name";
    public static final String INDEX_SOURCE_UPDATED = "idx_synced_cache_source_updated";
    public static final String INDEX_SOURCE_VERSION = "idx_synced_cache_source_version";

    private ContactsCacheContract() {
    }
}
