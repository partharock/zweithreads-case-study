package com.autotech.aaos.contactscache.android;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteStatement;

import com.autotech.aaos.contactscache.core.model.CachedContact;
import com.autotech.aaos.contactscache.core.model.ContactPayload;
import com.autotech.aaos.contactscache.core.model.SyncState;
import com.autotech.aaos.contactscache.core.model.UpsertOutcome;
import com.autotech.aaos.contactscache.core.store.ContactsCacheStore;
import com.autotech.aaos.contactscache.core.store.StoreTransaction;

import org.json.JSONArray;
import org.json.JSONException;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.Set;

public final class SqliteContactsCacheStore implements ContactsCacheStore {
    private final ContactsCacheDatabaseHelper dbHelper;

    public SqliteContactsCacheStore(ContactsCacheDatabaseHelper dbHelper) {
        this.dbHelper = Objects.requireNonNull(dbHelper, "dbHelper");
    }

    @Override
    public StoreTransaction beginTransaction() {
        SQLiteDatabase db = dbHelper.getWritableDatabase();
        db.beginTransactionNonExclusive();
        return new SqliteTx(db);
    }

    @Override
    public UpsertOutcome upsertContact(String sourceDevice, ContactPayload payload, long nowMs) {
        SQLiteDatabase db = dbHelper.getWritableDatabase();

        ExistingContact existing = queryExisting(db, sourceDevice, payload.getExternalContactId());
        if (existing == null) {
            ContentValues values = new ContentValues();
            values.put(ContactsCacheContract.COL_SOURCE_DEVICE, sourceDevice);
            values.put(ContactsCacheContract.COL_EXTERNAL_CONTACT_ID, payload.getExternalContactId());
            values.put(ContactsCacheContract.COL_DISPLAY_NAME, payload.getDisplayName());
            values.put(ContactsCacheContract.COL_PHONES_JSON, encodeList(payload.getPhones()));
            values.put(ContactsCacheContract.COL_EMAILS_JSON, encodeList(payload.getEmails()));
            values.put(ContactsCacheContract.COL_AVATAR_ETAG, payload.getAvatarEtag());
            values.put(ContactsCacheContract.COL_SOURCE_VERSION, payload.getSourceVersion());
            values.put(ContactsCacheContract.COL_SOURCE_LAST_MODIFIED_MS, payload.getSourceLastModifiedMs());
            values.put(ContactsCacheContract.COL_LOCAL_UPDATED_MS, nowMs);
            values.put(ContactsCacheContract.COL_DELETED, 0);
            db.insertOrThrow(ContactsCacheContract.TABLE_CONTACTS, null, values);
            return UpsertOutcome.INSERTED;
        }

        if (payload.getSourceVersion() < existing.sourceVersion) {
            return UpsertOutcome.STALE_IGNORED;
        }
        if (payload.getSourceVersion() == existing.sourceVersion
                && payload.getSourceLastModifiedMs() < existing.sourceLastModifiedMs) {
            return UpsertOutcome.STALE_IGNORED;
        }

        String phonesJson = encodeList(payload.getPhones());
        String emailsJson = encodeList(payload.getEmails());

        boolean unchanged = existing.deleted == 0
                && existing.displayName.equals(payload.getDisplayName())
                && existing.phonesJson.equals(phonesJson)
                && existing.emailsJson.equals(emailsJson)
                && Objects.equals(existing.avatarEtag, payload.getAvatarEtag())
                && existing.sourceVersion == payload.getSourceVersion()
                && existing.sourceLastModifiedMs == payload.getSourceLastModifiedMs();
        if (unchanged) {
            return UpsertOutcome.UNCHANGED;
        }

        ContentValues update = new ContentValues();
        update.put(ContactsCacheContract.COL_DISPLAY_NAME, payload.getDisplayName());
        update.put(ContactsCacheContract.COL_PHONES_JSON, phonesJson);
        update.put(ContactsCacheContract.COL_EMAILS_JSON, emailsJson);
        update.put(ContactsCacheContract.COL_AVATAR_ETAG, payload.getAvatarEtag());
        update.put(ContactsCacheContract.COL_SOURCE_VERSION, payload.getSourceVersion());
        update.put(ContactsCacheContract.COL_SOURCE_LAST_MODIFIED_MS, payload.getSourceLastModifiedMs());
        update.put(ContactsCacheContract.COL_LOCAL_UPDATED_MS, nowMs);
        update.put(ContactsCacheContract.COL_DELETED, 0);

        db.update(
                ContactsCacheContract.TABLE_CONTACTS,
                update,
                ContactsCacheContract.COL_SOURCE_DEVICE + "=? AND "
                        + ContactsCacheContract.COL_EXTERNAL_CONTACT_ID + "=?",
                new String[]{sourceDevice, payload.getExternalContactId()}
        );

        return UpsertOutcome.UPDATED;
    }

    @Override
    public int markDeleted(String sourceDevice, Set<String> externalContactIds, long nowMs) {
        if (externalContactIds == null || externalContactIds.isEmpty()) {
            return 0;
        }

        SQLiteDatabase db = dbHelper.getWritableDatabase();
        int changed = 0;
        for (String id : externalContactIds) {
            ContentValues values = new ContentValues();
            values.put(ContactsCacheContract.COL_DELETED, 1);
            values.put(ContactsCacheContract.COL_LOCAL_UPDATED_MS, nowMs);
            changed += db.update(
                    ContactsCacheContract.TABLE_CONTACTS,
                    values,
                    ContactsCacheContract.COL_SOURCE_DEVICE + "=? AND "
                            + ContactsCacheContract.COL_EXTERNAL_CONTACT_ID + "=? AND "
                            + ContactsCacheContract.COL_DELETED + "=0",
                    new String[]{sourceDevice, id}
            );
        }
        return changed;
    }

    @Override
    public int markMissingDeleted(String sourceDevice, Set<String> liveContactIds, long nowMs) {
        SQLiteDatabase db = dbHelper.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(ContactsCacheContract.COL_DELETED, 1);
        values.put(ContactsCacheContract.COL_LOCAL_UPDATED_MS, nowMs);

        if (liveContactIds == null || liveContactIds.isEmpty()) {
            return db.update(
                    ContactsCacheContract.TABLE_CONTACTS,
                    values,
                    ContactsCacheContract.COL_SOURCE_DEVICE + "=? AND "
                            + ContactsCacheContract.COL_DELETED + "=0",
                    new String[]{sourceDevice}
            );
        }

        List<String> args = new ArrayList<>();
        args.add(sourceDevice);
        args.addAll(liveContactIds);

        String placeholders = String.join(",", Collections.nCopies(liveContactIds.size(), "?"));
        String where = ContactsCacheContract.COL_SOURCE_DEVICE + "=? AND "
                + ContactsCacheContract.COL_DELETED + "=0 AND "
                + ContactsCacheContract.COL_EXTERNAL_CONTACT_ID + " NOT IN (" + placeholders + ")";

        return db.update(
                ContactsCacheContract.TABLE_CONTACTS,
                values,
                where,
                args.toArray(new String[0])
        );
    }

    @Override
    public int purgeDeletedBefore(long cutoffMs) {
        SQLiteDatabase db = dbHelper.getWritableDatabase();
        return db.delete(
                ContactsCacheContract.TABLE_CONTACTS,
                ContactsCacheContract.COL_DELETED + "=1 AND "
                        + ContactsCacheContract.COL_LOCAL_UPDATED_MS + "<?",
                new String[]{Long.toString(cutoffMs)}
        );
    }

    @Override
    public List<CachedContact> listActiveContacts(String sourceDevice, String namePrefix, int limit) {
        SQLiteDatabase db = dbHelper.getReadableDatabase();

        String selection = ContactsCacheContract.COL_SOURCE_DEVICE + "=? AND "
                + ContactsCacheContract.COL_DELETED + "=0";
        List<String> args = new ArrayList<>();
        args.add(sourceDevice);

        if (namePrefix != null && !namePrefix.isBlank()) {
            selection += " AND " + ContactsCacheContract.COL_DISPLAY_NAME + " LIKE ?";
            args.add(namePrefix + "%");
        }

        String limitArg = limit > 0 ? Integer.toString(limit) : null;

        try (Cursor cursor = db.query(
                ContactsCacheContract.TABLE_CONTACTS,
                new String[]{
                        ContactsCacheContract.COL_SOURCE_DEVICE,
                        ContactsCacheContract.COL_EXTERNAL_CONTACT_ID,
                        ContactsCacheContract.COL_DISPLAY_NAME,
                        ContactsCacheContract.COL_PHONES_JSON,
                        ContactsCacheContract.COL_EMAILS_JSON,
                        ContactsCacheContract.COL_AVATAR_ETAG,
                        ContactsCacheContract.COL_SOURCE_VERSION,
                        ContactsCacheContract.COL_SOURCE_LAST_MODIFIED_MS,
                        ContactsCacheContract.COL_LOCAL_UPDATED_MS
                },
                selection,
                args.toArray(new String[0]),
                null,
                null,
                ContactsCacheContract.COL_DISPLAY_NAME + " COLLATE NOCASE ASC",
                limitArg
        )) {
            List<CachedContact> contacts = new ArrayList<>();
            while (cursor.moveToNext()) {
                contacts.add(new CachedContact(
                        cursor.getString(0),
                        cursor.getString(1),
                        cursor.getString(2),
                        decodeList(cursor.getString(3)),
                        decodeList(cursor.getString(4)),
                        cursor.getString(5),
                        cursor.getLong(6),
                        cursor.getLong(7),
                        cursor.getLong(8)
                ));
            }
            return contacts;
        }
    }

    @Override
    public SyncState getSyncState(String sourceDevice) {
        SQLiteDatabase db = dbHelper.getReadableDatabase();
        try (Cursor cursor = db.query(
                ContactsCacheContract.TABLE_SYNC_STATE,
                new String[]{
                        ContactsCacheContract.COL_SOURCE_DEVICE,
                        ContactsCacheContract.COL_LAST_FULL_SYNC_MS,
                        ContactsCacheContract.COL_LAST_SYNC_TOKEN,
                        ContactsCacheContract.COL_LAST_SOURCE_SYNC_SEQUENCE,
                        ContactsCacheContract.COL_CACHE_SCHEMA_VERSION
                },
                ContactsCacheContract.COL_SOURCE_DEVICE + "=?",
                new String[]{sourceDevice},
                null,
                null,
                null
        )) {
            if (!cursor.moveToFirst()) {
                return null;
            }
            return new SyncState(
                    cursor.getString(0),
                    cursor.getLong(1),
                    cursor.getString(2),
                    cursor.getLong(3),
                    cursor.getInt(4)
            );
        }
    }

    @Override
    public void upsertSyncState(
            String sourceDevice,
            long lastFullSyncMs,
            String lastSyncToken,
            long lastSourceSyncSequence,
            int cacheSchemaVersion
    ) {
        SQLiteDatabase db = dbHelper.getWritableDatabase();

        ContentValues values = new ContentValues();
        values.put(ContactsCacheContract.COL_SOURCE_DEVICE, sourceDevice);
        values.put(ContactsCacheContract.COL_LAST_FULL_SYNC_MS, lastFullSyncMs);
        values.put(ContactsCacheContract.COL_LAST_SYNC_TOKEN, lastSyncToken);
        values.put(ContactsCacheContract.COL_LAST_SOURCE_SYNC_SEQUENCE, lastSourceSyncSequence);
        values.put(ContactsCacheContract.COL_CACHE_SCHEMA_VERSION, cacheSchemaVersion);

        long result = db.insertWithOnConflict(
                ContactsCacheContract.TABLE_SYNC_STATE,
                null,
                values,
                SQLiteDatabase.CONFLICT_REPLACE
        );
        if (result == -1L) {
            throw new IllegalStateException("Failed to upsert sync state for source=" + sourceDevice);
        }
    }

    @Override
    public int countActiveContacts(String sourceDevice) {
        SQLiteDatabase db = dbHelper.getReadableDatabase();
        String sql = "SELECT COUNT(*) FROM " + ContactsCacheContract.TABLE_CONTACTS + " WHERE "
                + ContactsCacheContract.COL_SOURCE_DEVICE + "=? AND "
                + ContactsCacheContract.COL_DELETED + "=0";
        SQLiteStatement statement = db.compileStatement(sql);
        statement.bindString(1, sourceDevice);
        return (int) statement.simpleQueryForLong();
    }

    private ExistingContact queryExisting(SQLiteDatabase db, String sourceDevice, String externalContactId) {
        try (Cursor cursor = db.query(
                ContactsCacheContract.TABLE_CONTACTS,
                new String[]{
                        ContactsCacheContract.COL_DISPLAY_NAME,
                        ContactsCacheContract.COL_PHONES_JSON,
                        ContactsCacheContract.COL_EMAILS_JSON,
                        ContactsCacheContract.COL_AVATAR_ETAG,
                        ContactsCacheContract.COL_SOURCE_VERSION,
                        ContactsCacheContract.COL_SOURCE_LAST_MODIFIED_MS,
                        ContactsCacheContract.COL_DELETED
                },
                ContactsCacheContract.COL_SOURCE_DEVICE + "=? AND "
                        + ContactsCacheContract.COL_EXTERNAL_CONTACT_ID + "=?",
                new String[]{sourceDevice, externalContactId},
                null,
                null,
                null
        )) {
            if (!cursor.moveToFirst()) {
                return null;
            }
            return new ExistingContact(
                    cursor.getString(0),
                    cursor.getString(1),
                    cursor.getString(2),
                    cursor.getString(3),
                    cursor.getLong(4),
                    cursor.getLong(5),
                    cursor.getInt(6)
            );
        }
    }

    private static String encodeList(List<String> values) {
        JSONArray array = new JSONArray();
        for (String value : values) {
            array.put(value);
        }
        return array.toString();
    }

    private static List<String> decodeList(String json) {
        if (json == null || json.isBlank()) {
            return List.of();
        }
        try {
            JSONArray array = new JSONArray(json);
            List<String> values = new ArrayList<>(array.length());
            for (int i = 0; i < array.length(); i++) {
                values.add(array.optString(i, ""));
            }
            return values;
        } catch (JSONException exception) {
            return List.of();
        }
    }

    private static final class SqliteTx implements StoreTransaction {
        private final SQLiteDatabase db;
        private boolean closed;

        private SqliteTx(SQLiteDatabase db) {
            this.db = db;
        }

        @Override
        public void commit() {
            if (closed) {
                throw new IllegalStateException("Transaction already closed");
            }
            db.setTransactionSuccessful();
            db.endTransaction();
            closed = true;
        }

        @Override
        public void close() {
            if (closed) {
                return;
            }
            db.endTransaction();
            closed = true;
        }
    }

    private static final class ExistingContact {
        private final String displayName;
        private final String phonesJson;
        private final String emailsJson;
        private final String avatarEtag;
        private final long sourceVersion;
        private final long sourceLastModifiedMs;
        private final int deleted;

        private ExistingContact(
                String displayName,
                String phonesJson,
                String emailsJson,
                String avatarEtag,
                long sourceVersion,
                long sourceLastModifiedMs,
                int deleted
        ) {
            this.displayName = displayName;
            this.phonesJson = phonesJson;
            this.emailsJson = emailsJson;
            this.avatarEtag = avatarEtag;
            this.sourceVersion = sourceVersion;
            this.sourceLastModifiedMs = sourceLastModifiedMs;
            this.deleted = deleted;
        }
    }
}
