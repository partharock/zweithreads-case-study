package com.autotech.aaos.contactscache.android;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

public final class ContactsCacheDatabaseHelper extends SQLiteOpenHelper {
    public ContactsCacheDatabaseHelper(Context context) {
        super(context, ContactsCacheContract.DB_NAME, null, ContactsCacheContract.DB_VERSION);
    }

    @Override
    public void onConfigure(SQLiteDatabase db) {
        db.setForeignKeyConstraintsEnabled(true);
        db.enableWriteAheadLogging();
        db.execSQL("PRAGMA synchronous=NORMAL");
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        createTables(db);
        createIndexes(db);
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 1) {
            createTables(db);
            createIndexes(db);
        }
        if (oldVersion < 2) {
            createVersion2Indexes(db);
        }
    }

    private static void createTables(SQLiteDatabase db) {
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
    }

    private static void createIndexes(SQLiteDatabase db) {
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

        createVersion2Indexes(db);
    }

    private static void createVersion2Indexes(SQLiteDatabase db) {
        db.execSQL(
                "CREATE INDEX IF NOT EXISTS " + ContactsCacheContract.INDEX_SOURCE_VERSION
                        + " ON " + ContactsCacheContract.TABLE_CONTACTS + "("
                        + ContactsCacheContract.COL_SOURCE_DEVICE + ","
                        + ContactsCacheContract.COL_SOURCE_VERSION + ","
                        + ContactsCacheContract.COL_SOURCE_LAST_MODIFIED_MS
                        + ")"
        );
    }
}
