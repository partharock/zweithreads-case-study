package com.autotech.aaos.contactscache.integration;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import android.content.Context;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.autotech.aaos.contactscache.android.ContactsCacheContract;
import com.autotech.aaos.contactscache.android.ContactsCacheDatabaseHelper;
import com.autotech.aaos.contactscache.android.SqliteContactsCacheStore;
import com.autotech.aaos.contactscache.core.model.CachedContact;
import com.autotech.aaos.contactscache.core.model.ContactPayload;
import com.autotech.aaos.contactscache.core.model.SyncMetadata;
import com.autotech.aaos.contactscache.core.model.SyncSummary;
import com.autotech.aaos.contactscache.core.sync.ContactSyncEngine;
import com.autotech.aaos.contactscache.core.sync.SyncRejectedException;
import com.autotech.aaos.contactscache.core.util.Clock;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.List;

@RunWith(AndroidJUnit4.class)
public final class ContactsCacheStoreIntegrationTest {
    private Context context;
    private ContactsCacheDatabaseHelper dbHelper;
    private SqliteContactsCacheStore store;
    private ContactSyncEngine syncEngine;

    @Before
    public void setUp() {
        context = ApplicationProvider.getApplicationContext();
        context.deleteDatabase(ContactsCacheContract.DB_NAME);

        dbHelper = new ContactsCacheDatabaseHelper(context);
        store = new SqliteContactsCacheStore(dbHelper);
        Clock fixedClock = () -> 1700000000000L;
        syncEngine = new ContactSyncEngine(store, com.autotech.aaos.contactscache.core.model.CacheLimits.productionDefaults(), fixedClock);
    }

    @After
    public void tearDown() {
        if (dbHelper != null) {
            dbHelper.close();
        }
        context.deleteDatabase(ContactsCacheContract.DB_NAME);
    }

    @Test
    public void fullSync_persistsAcrossDatabaseReopen() {
        SyncSummary summary = syncEngine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("c1", "Alex Kim", "+1 555-0100", "alex@example.com", 1, 100),
                        contact("c2", "Priya Raman", "+1 555-0102", "priya@example.com", 1, 100)
                ),
                SyncMetadata.full("token-1", 10L, true)
        );

        assertEquals(2, summary.getInserted());
        assertEquals(0, summary.getDeleted());

        dbHelper.close();
        dbHelper = new ContactsCacheDatabaseHelper(context);
        store = new SqliteContactsCacheStore(dbHelper);

        List<CachedContact> contacts = store.listActiveContacts("pixel8-bt", null, 50);
        assertEquals(2, contacts.size());
        assertEquals("Alex Kim", contacts.get(0).getDisplayName());
        assertEquals("Priya Raman", contacts.get(1).getDisplayName());
    }

    @Test
    public void deltaSync_updatesAndDeletesCorrectRows() {
        syncEngine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("c1", "Alex", "+1 555-0100", "alex@example.com", 1, 100),
                        contact("c2", "Priya", "+1 555-0102", "priya@example.com", 1, 100)
                ),
                SyncMetadata.full("token-1", 11L, true)
        );

        SyncSummary summary = syncEngine.applyDeltaSync(
                "pixel8-bt",
                List.of(contact("c2", "Priya", "+1 555-9999", "priya@example.com", 2, 200)),
                List.of("c1"),
                SyncMetadata.delta("token-2", 12L)
        );

        assertEquals(1, summary.getUpdated());
        assertEquals(1, summary.getDeleted());

        List<CachedContact> contacts = store.listActiveContacts("pixel8-bt", null, 50);
        assertEquals(1, contacts.size());
        assertEquals("c2", contacts.get(0).getExternalContactId());
        assertEquals("+15559999", contacts.get(0).getPhones().get(0));
    }

    @Test
    public void fullSync_partialSnapshot_doesNotDeleteMissingContacts() {
        syncEngine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("c1", "Alex", "+1 555-0100", "alex@example.com", 1, 100),
                        contact("c2", "Priya", "+1 555-0102", "priya@example.com", 1, 100)
                ),
                SyncMetadata.full("token-1", 13L, true)
        );

        SyncSummary summary = syncEngine.applyFullSync(
                "pixel8-bt",
                List.of(contact("c2", "Priya", "+1 555-0102", "priya@example.com", 1, 100)),
                SyncMetadata.full("token-2", 14L, false)
        );

        assertTrue(summary.isPartialSnapshot());
        assertEquals(0, summary.getDeleted());
        assertEquals(2, store.countActiveContacts("pixel8-bt"));
    }

    @Test(expected = SyncRejectedException.class)
    public void syncSequence_regressionIsRejected() {
        syncEngine.applyFullSync(
                "pixel8-bt",
                List.of(contact("c1", "Alex", "+1 555-0100", "alex@example.com", 1, 100)),
                SyncMetadata.full("token-1", 100L, true)
        );

        syncEngine.applyDeltaSync(
                "pixel8-bt",
                List.of(contact("c1", "Alex", "+1 555-0199", "alex@example.com", 2, 101)),
                List.of(),
                SyncMetadata.delta("token-2", 99L)
        );
    }

    private static ContactPayload contact(
            String id,
            String name,
            String phone,
            String email,
            long sourceVersion,
            long sourceLastModifiedMs
    ) {
        return new ContactPayload(
                id,
                name,
                List.of(phone),
                List.of(email),
                null,
                sourceVersion,
                sourceLastModifiedMs
        );
    }
}
