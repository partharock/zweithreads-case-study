package com.autotech.aaos.contactscache.integration;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.autotech.aaos.contactscache.android.ContactsCacheContract;
import com.autotech.aaos.contactscache.android.ContactsCacheDatabaseHelper;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public final class ContactsCacheDatabaseMigrationTest {
    private Context context;

    @Before
    public void setUp() {
        context = ApplicationProvider.getApplicationContext();
        context.deleteDatabase(ContactsCacheContract.DB_NAME);
    }

    @After
    public void tearDown() {
        context.deleteDatabase(ContactsCacheContract.DB_NAME);
    }

    @Test
    public void upgrade_fromV1ToV2_createsSourceVersionIndex() {
        String dbPath = context.getDatabasePath(ContactsCacheContract.DB_NAME).getAbsolutePath();

        SQLiteDatabase legacyDb = SQLiteDatabase.openOrCreateDatabase(dbPath, null);
        try {
            createV1Schema(legacyDb);
            legacyDb.setVersion(1);
        } finally {
            legacyDb.close();
        }

        ContactsCacheDatabaseHelper helper = new ContactsCacheDatabaseHelper(context);
        SQLiteDatabase upgradedDb = helper.getWritableDatabase();
        try {
            assertEquals(ContactsCacheContract.DB_VERSION, upgradedDb.getVersion());
            assertTrue(hasIndex(upgradedDb, ContactsCacheContract.INDEX_SOURCE_VERSION));
        } finally {
            helper.close();
        }
    }

    @Test
    public void freshCreate_enablesWalAndCreatesRequiredIndexes() {
        ContactsCacheDatabaseHelper helper = new ContactsCacheDatabaseHelper(context);
        SQLiteDatabase db = helper.getWritableDatabase();
        try {
            assertTrue(hasIndex(db, ContactsCacheContract.INDEX_SOURCE_DELETED_NAME));
            assertTrue(hasIndex(db, ContactsCacheContract.INDEX_SOURCE_UPDATED));
            assertTrue(hasIndex(db, ContactsCacheContract.INDEX_SOURCE_VERSION));

            try (Cursor cursor = db.rawQuery("PRAGMA journal_mode", null)) {
                assertTrue(cursor.moveToFirst());
                String mode = cursor.getString(0);
                assertEquals("wal", mode.toLowerCase());
            }
        } finally {
            helper.close();
        }
    }

    private static void createV1Schema(SQLiteDatabase db) {
        db.execSQL(
                "CREATE TABLE IF NOT EXISTS " + ContactsCacheContract.TABLE_CONTACTS + " ("
                        + ContactsCacheContract.COL_SOURCE_DEVICE + " TEXT NOT NULL,"
                        + ContactsCacheContract.COL_EXTERNAL_CONTACT_ID + " TEXT NOT NULL,"
                        + ContactsCacheContract.COL_DISPLAY_NAME + " TEXT NOT NULL,"
                        + ContactsCacheContract.COL_PHONES_JSON + " TEXT NOT NULL,"
                        + ContactsCacheContract.COL_EMAILS_JSON + " TEXT NOT NULL,"
                        + ContactsCacheContract.COL_AVATAR_ETAG + " TEXT,"
                        + ContactsCacheContract.COL_SOURCE_VERSION + " INTEGER NOT NULL,"
                        + ContactsCacheContract.COL_SOURCE_LAST_MODIFIED_MS + " INTEGER NOT NULL,"
                        + ContactsCacheContract.COL_LOCAL_UPDATED_MS + " INTEGER NOT NULL,"
                        + ContactsCacheContract.COL_DELETED + " INTEGER NOT NULL DEFAULT 0 CHECK ("
                        + ContactsCacheContract.COL_DELETED + " IN (0,1)),"
                        + "PRIMARY KEY ("
                        + ContactsCacheContract.COL_SOURCE_DEVICE + ","
                        + ContactsCacheContract.COL_EXTERNAL_CONTACT_ID + ")"
                        + ")"
        );

        db.execSQL(
                "CREATE TABLE IF NOT EXISTS " + ContactsCacheContract.TABLE_SYNC_STATE + " ("
                        + ContactsCacheContract.COL_SOURCE_DEVICE + " TEXT PRIMARY KEY,"
                        + ContactsCacheContract.COL_LAST_FULL_SYNC_MS + " INTEGER NOT NULL,"
                        + ContactsCacheContract.COL_LAST_SYNC_TOKEN + " TEXT,"
                        + ContactsCacheContract.COL_LAST_SOURCE_SYNC_SEQUENCE + " INTEGER NOT NULL,"
                        + ContactsCacheContract.COL_CACHE_SCHEMA_VERSION + " INTEGER NOT NULL"
                        + ")"
        );

        db.execSQL(
                "CREATE INDEX IF NOT EXISTS " + ContactsCacheContract.INDEX_SOURCE_DELETED_NAME
                        + " ON " + ContactsCacheContract.TABLE_CONTACTS + "("
                        + ContactsCacheContract.COL_SOURCE_DEVICE + ","
                        + ContactsCacheContract.COL_DELETED + ","
                        + ContactsCacheContract.COL_DISPLAY_NAME
                        + ")"
        );

        db.execSQL(
                "CREATE INDEX IF NOT EXISTS " + ContactsCacheContract.INDEX_SOURCE_UPDATED
                        + " ON " + ContactsCacheContract.TABLE_CONTACTS + "("
                        + ContactsCacheContract.COL_SOURCE_DEVICE + ","
                        + ContactsCacheContract.COL_LOCAL_UPDATED_MS
                        + ")"
        );
    }

    private static boolean hasIndex(SQLiteDatabase db, String indexName) {
        try (Cursor cursor = db.rawQuery(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                new String[]{indexName}
        )) {
            return cursor.moveToFirst();
        }
    }
}
