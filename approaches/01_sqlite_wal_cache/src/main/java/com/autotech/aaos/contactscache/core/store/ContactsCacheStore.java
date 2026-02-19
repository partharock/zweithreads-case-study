package com.autotech.aaos.contactscache.core.store;

import com.autotech.aaos.contactscache.core.model.CachedContact;
import com.autotech.aaos.contactscache.core.model.ContactPayload;
import com.autotech.aaos.contactscache.core.model.SyncState;
import com.autotech.aaos.contactscache.core.model.UpsertOutcome;

import java.util.List;
import java.util.Set;

public interface ContactsCacheStore {
    StoreTransaction beginTransaction();

    UpsertOutcome upsertContact(String sourceDevice, ContactPayload payload, long nowMs);

    int markDeleted(String sourceDevice, Set<String> externalContactIds, long nowMs);

    int markMissingDeleted(String sourceDevice, Set<String> liveContactIds, long nowMs);

    int purgeDeletedBefore(long cutoffMs);

    List<CachedContact> listActiveContacts(String sourceDevice, String namePrefix, int limit);

    SyncState getSyncState(String sourceDevice);

    void upsertSyncState(
            String sourceDevice,
            long lastFullSyncMs,
            String lastSyncToken,
            long lastSourceSyncSequence,
            int cacheSchemaVersion
    );

    int countActiveContacts(String sourceDevice);
}
