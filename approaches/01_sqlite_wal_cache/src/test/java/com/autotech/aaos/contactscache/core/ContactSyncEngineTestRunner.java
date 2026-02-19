package com.autotech.aaos.contactscache.core;

import com.autotech.aaos.contactscache.core.model.CacheLimits;
import com.autotech.aaos.contactscache.core.model.CachedContact;
import com.autotech.aaos.contactscache.core.model.ContactPayload;
import com.autotech.aaos.contactscache.core.model.SyncMetadata;
import com.autotech.aaos.contactscache.core.model.SyncSummary;
import com.autotech.aaos.contactscache.core.sync.ContactSyncEngine;
import com.autotech.aaos.contactscache.core.sync.SyncRejectedException;
import com.autotech.aaos.contactscache.core.util.Clock;
import com.autotech.aaos.contactscache.inmemory.InMemoryContactsCacheStore;

import java.util.List;

public final class ContactSyncEngineTestRunner {
    private ContactSyncEngineTestRunner() {
    }

    public static void main(String[] args) {
        run("fullSync_insertsAndCounts", ContactSyncEngineTestRunner::fullSync_insertsAndCounts);
        run("fullSync_completeSnapshotDeletesMissing", ContactSyncEngineTestRunner::fullSync_completeSnapshotDeletesMissing);
        run("fullSync_partialSnapshotDoesNotDelete", ContactSyncEngineTestRunner::fullSync_partialSnapshotDoesNotDelete);
        run("deltaSync_upsertDeleteConflictKeepsUpsert", ContactSyncEngineTestRunner::deltaSync_upsertDeleteConflictKeepsUpsert);
        run("staleVersion_isIgnored", ContactSyncEngineTestRunner::staleVersion_isIgnored);
        run("sequenceRegression_isRejected", ContactSyncEngineTestRunner::sequenceRegression_isRejected);
        run("duplicateIds_keepNewest", ContactSyncEngineTestRunner::duplicateIds_keepNewest);
        run("normalization_trimsAndDedupes", ContactSyncEngineTestRunner::normalization_trimsAndDedupes);
        run("multiDevice_isolation", ContactSyncEngineTestRunner::multiDevice_isolation);
        run("limits_rejectOversizedSync", ContactSyncEngineTestRunner::limits_rejectOversizedSync);

        System.out.println("All tests passed.");
    }

    private static void fullSync_insertsAndCounts() {
        Fixture fixture = fixture(1_000L);

        SyncSummary summary = fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("c1", "Alex", List.of("+1 555-0001"), List.of("ALEX@EXAMPLE.COM"), 1, 100),
                        contact("c2", "Priya", List.of("+1 555-0002"), List.of("priya@example.com"), 1, 100)
                ),
                SyncMetadata.full("token-1", 10L, true)
        );

        assertEquals(2, summary.getInserted(), "inserted");
        assertEquals(0, summary.getDeleted(), "deleted");
        assertEquals(0, summary.getInvalidDropped(), "invalidDropped");
        assertEquals(2, fixture.store.countActiveContacts("pixel8-bt"), "active count");
    }

    private static void fullSync_completeSnapshotDeletesMissing() {
        Fixture fixture = fixture(2_000L);

        fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("c1", "Alex", List.of("+1-555-0001"), List.of(), 1, 100),
                        contact("c2", "Priya", List.of("+1-555-0002"), List.of(), 1, 100)
                ),
                SyncMetadata.full("token-1", 11L, true)
        );

        SyncSummary summary = fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(contact("c2", "Priya", List.of("+1-555-0002"), List.of(), 1, 100)),
                SyncMetadata.full("token-2", 12L, true)
        );

        assertEquals(1, summary.getDeleted(), "deleted after full sync");
        assertEquals(1, fixture.store.countActiveContacts("pixel8-bt"), "active count after delete");
    }

    private static void fullSync_partialSnapshotDoesNotDelete() {
        Fixture fixture = fixture(3_000L);

        fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("c1", "Alex", List.of("+1-555-0001"), List.of(), 1, 100),
                        contact("c2", "Priya", List.of("+1-555-0002"), List.of(), 1, 100)
                ),
                SyncMetadata.full("token-1", 13L, true)
        );

        SyncSummary summary = fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(contact("c2", "Priya", List.of("+1-555-0002"), List.of(), 1, 100)),
                SyncMetadata.full("token-2", 14L, false)
        );

        assertEquals(0, summary.getDeleted(), "deleted with partial snapshot");
        assertEquals(2, fixture.store.countActiveContacts("pixel8-bt"), "active count with partial snapshot");
    }

    private static void deltaSync_upsertDeleteConflictKeepsUpsert() {
        Fixture fixture = fixture(4_000L);

        fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(contact("c1", "Alex", List.of("+1-555-0001"), List.of(), 1, 100)),
                SyncMetadata.full("token-1", 15L, true)
        );

        SyncSummary summary = fixture.engine.applyDeltaSync(
                "pixel8-bt",
                List.of(contact("c1", "Alex", List.of("+1-555-7777"), List.of(), 2, 200)),
                List.of("c1"),
                SyncMetadata.delta("token-2", 16L)
        );

        assertEquals(1, summary.getUpdated(), "updated");
        assertEquals(0, summary.getDeleted(), "deleted (conflict removed)");

        List<CachedContact> active = fixture.store.listActiveContacts("pixel8-bt", null, 10);
        assertEquals(1, active.size(), "active size");
        assertEquals("+15557777", active.get(0).getPhones().get(0), "phone updated");
    }

    private static void staleVersion_isIgnored() {
        Fixture fixture = fixture(5_000L);

        fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(contact("c1", "Alex", List.of("+1-555-0001"), List.of(), 2, 200)),
                SyncMetadata.full("token-1", 17L, true)
        );

        SyncSummary summary = fixture.engine.applyDeltaSync(
                "pixel8-bt",
                List.of(contact("c1", "Alex", List.of("+1-555-9999"), List.of(), 1, 100)),
                List.of(),
                SyncMetadata.delta("token-2", 18L)
        );

        assertEquals(1, summary.getStaleIgnored(), "stale ignored");
        List<CachedContact> active = fixture.store.listActiveContacts("pixel8-bt", null, 10);
        assertEquals("+15550001", active.get(0).getPhones().get(0), "stale phone not applied");
    }

    private static void sequenceRegression_isRejected() {
        Fixture fixture = fixture(6_000L);

        fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(contact("c1", "Alex", List.of("+1-555-0001"), List.of(), 1, 100)),
                SyncMetadata.full("token-1", 20L, true)
        );

        boolean rejected = false;
        try {
            fixture.engine.applyDeltaSync(
                    "pixel8-bt",
                    List.of(contact("c1", "Alex", List.of("+1-555-0002"), List.of(), 2, 200)),
                    List.of(),
                    SyncMetadata.delta("token-2", 19L)
            );
        } catch (SyncRejectedException expected) {
            rejected = true;
        }

        assertTrue(rejected, "sequence regression should be rejected");
    }

    private static void duplicateIds_keepNewest() {
        Fixture fixture = fixture(7_000L);

        SyncSummary summary = fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("dup", "Alex", List.of("+1-555-1000"), List.of(), 1, 100),
                        contact("dup", "Alex", List.of("+1-555-2000"), List.of(), 3, 300)
                ),
                SyncMetadata.full("token-1", 21L, true)
        );

        assertEquals(1, summary.getInserted(), "only one inserted after dedupe");
        List<CachedContact> active = fixture.store.listActiveContacts("pixel8-bt", null, 10);
        assertEquals("+15552000", active.get(0).getPhones().get(0), "newest duplicate wins");
    }

    private static void normalization_trimsAndDedupes() {
        Fixture fixture = fixture(8_000L);

        SyncSummary summary = fixture.engine.applyFullSync(
                "pixel8-bt",
                List.of(
                        contact("  c1  ", "   ", List.of("+1 (555) 123-4567", "+1 555 123 4567", "bad"),
                                List.of("USER@EXAMPLE.COM", "user@example.com", "no-at-sign"), 1, 100),
                        contact("   ", "invalid", List.of(), List.of(), 1, 100)
                ),
                SyncMetadata.full("token-1", 22L, true)
        );

        assertEquals(1, summary.getInvalidDropped(), "invalid contact dropped");
        List<CachedContact> active = fixture.store.listActiveContacts("pixel8-bt", null, 10);
        assertEquals(1, active.size(), "active size");
        assertEquals("Unknown", active.get(0).getDisplayName(), "blank name fallback");
        assertEquals(1, active.get(0).getPhones().size(), "dedupe phones");
        assertEquals(1, active.get(0).getEmails().size(), "dedupe emails");
        assertEquals("user@example.com", active.get(0).getEmails().get(0), "lowercase email");
    }

    private static void multiDevice_isolation() {
        Fixture fixture = fixture(9_000L);

        fixture.engine.applyFullSync(
                "device-a",
                List.of(contact("c1", "Alex", List.of("+1-555-0001"), List.of(), 1, 100)),
                SyncMetadata.full("token-a", 23L, true)
        );
        fixture.engine.applyFullSync(
                "device-b",
                List.of(contact("c1", "Bianca", List.of("+1-555-9999"), List.of(), 1, 100)),
                SyncMetadata.full("token-b", 24L, true)
        );

        assertEquals(1, fixture.store.countActiveContacts("device-a"), "device-a count");
        assertEquals(1, fixture.store.countActiveContacts("device-b"), "device-b count");
        assertEquals(
                "Alex",
                fixture.store.listActiveContacts("device-a", null, 10).get(0).getDisplayName(),
                "device-a contact"
        );
    }

    private static void limits_rejectOversizedSync() {
        InMemoryContactsCacheStore store = new InMemoryContactsCacheStore();
        CacheLimits tinyLimits = new CacheLimits(1, 5, 5, 64, 32, 64, 32, 32);
        Clock fixedClock = () -> 10_000L;
        ContactSyncEngine engine = new ContactSyncEngine(store, tinyLimits, fixedClock);

        boolean rejected = false;
        try {
            engine.applyFullSync(
                    "pixel8-bt",
                    List.of(
                            contact("c1", "Alex", List.of("+1-555-0001"), List.of(), 1, 100),
                            contact("c2", "Priya", List.of("+1-555-0002"), List.of(), 1, 100)
                    ),
                    SyncMetadata.full("token", 25L, true)
            );
        } catch (SyncRejectedException expected) {
            rejected = true;
        }

        assertTrue(rejected, "limit should reject oversized sync");
    }

    private static Fixture fixture(long nowMs) {
        InMemoryContactsCacheStore store = new InMemoryContactsCacheStore();
        Clock fixedClock = () -> nowMs;
        ContactSyncEngine engine = new ContactSyncEngine(store, CacheLimits.productionDefaults(), fixedClock);
        return new Fixture(store, engine);
    }

    private static ContactPayload contact(
            String id,
            String name,
            List<String> phones,
            List<String> emails,
            long version,
            long modifiedMs
    ) {
        return new ContactPayload(id, name, phones, emails, null, version, modifiedMs);
    }

    private static void run(String name, TestCase testCase) {
        try {
            testCase.run();
            System.out.println("[PASS] " + name);
        } catch (Throwable t) {
            System.err.println("[FAIL] " + name + " -> " + t.getMessage());
            t.printStackTrace(System.err);
            System.exit(1);
        }
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!java.util.Objects.equals(expected, actual)) {
            throw new AssertionError(label + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void assertTrue(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError(label + " expected=true actual=false");
        }
    }

    @FunctionalInterface
    private interface TestCase {
        void run();
    }

    private static final class Fixture {
        private final InMemoryContactsCacheStore store;
        private final ContactSyncEngine engine;

        private Fixture(InMemoryContactsCacheStore store, ContactSyncEngine engine) {
            this.store = store;
            this.engine = engine;
        }
    }
}
