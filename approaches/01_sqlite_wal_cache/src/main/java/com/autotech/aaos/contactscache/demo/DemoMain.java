package com.autotech.aaos.contactscache.demo;

import com.autotech.aaos.contactscache.core.model.ContactPayload;
import com.autotech.aaos.contactscache.core.model.SyncMetadata;
import com.autotech.aaos.contactscache.core.sync.ContactSyncEngine;
import com.autotech.aaos.contactscache.inmemory.InMemoryContactsCacheStore;

import java.util.List;

public final class DemoMain {
    private DemoMain() {
    }

    public static void main(String[] args) {
        InMemoryContactsCacheStore store = new InMemoryContactsCacheStore();
        ContactSyncEngine engine = new ContactSyncEngine(store);

        System.out.println(engine.applyFullSync(
                "pixel8-bt",
                List.of(
                        new ContactPayload("c1", "Alex Kim", List.of("+1-555-0100"), List.of("alex@example.com"), null, 1, 100),
                        new ContactPayload("c2", "Priya Raman", List.of("+1-555-0122"), List.of("priya@example.com"), null, 1, 100)
                ),
                SyncMetadata.full("token-1", 1, true)
        ));

        System.out.println(engine.applyDeltaSync(
                "pixel8-bt",
                List.of(new ContactPayload("c2", "Priya Raman", List.of("+1-555-9999"), List.of("priya@example.com"), null, 2, 200)),
                List.of("c1"),
                SyncMetadata.delta("token-2", 2)
        ));

        store.listActiveContacts("pixel8-bt", null, 50)
                .forEach(c -> System.out.println(c.getDisplayName() + " -> " + c.getPhones()));
    }
}
