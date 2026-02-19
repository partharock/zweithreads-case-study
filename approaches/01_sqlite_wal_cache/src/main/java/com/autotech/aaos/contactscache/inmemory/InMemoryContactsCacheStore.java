package com.autotech.aaos.contactscache.inmemory;

import com.autotech.aaos.contactscache.core.model.CachedContact;
import com.autotech.aaos.contactscache.core.model.ContactPayload;
import com.autotech.aaos.contactscache.core.model.SyncState;
import com.autotech.aaos.contactscache.core.model.UpsertOutcome;
import com.autotech.aaos.contactscache.core.store.ContactsCacheStore;
import com.autotech.aaos.contactscache.core.store.StoreTransaction;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public final class InMemoryContactsCacheStore implements ContactsCacheStore {
    private Map<String, Map<String, MutableContact>> contactsByDevice = new HashMap<>();
    private Map<String, SyncState> syncStateByDevice = new HashMap<>();

    private boolean inTransaction;
    private Map<String, Map<String, MutableContact>> txContactsSnapshot;
    private Map<String, SyncState> txSyncStateSnapshot;

    @Override
    public synchronized StoreTransaction beginTransaction() {
        if (inTransaction) {
            throw new IllegalStateException("Nested transactions are not supported");
        }
        inTransaction = true;
        txContactsSnapshot = deepCopyContacts(contactsByDevice);
        txSyncStateSnapshot = new HashMap<>(syncStateByDevice);
        return new Tx(this);
    }

    @Override
    public synchronized UpsertOutcome upsertContact(String sourceDevice, ContactPayload payload, long nowMs) {
        requireActiveTransaction();

        Map<String, MutableContact> deviceContacts = contactsByDevice.computeIfAbsent(
                sourceDevice,
                ignored -> new LinkedHashMap<>()
        );
        MutableContact existing = deviceContacts.get(payload.getExternalContactId());

        if (existing == null) {
            deviceContacts.put(payload.getExternalContactId(), MutableContact.fromPayload(payload, nowMs));
            return UpsertOutcome.INSERTED;
        }

        if (payload.getSourceVersion() < existing.sourceVersion) {
            return UpsertOutcome.STALE_IGNORED;
        }

        if (payload.getSourceVersion() == existing.sourceVersion
                && payload.getSourceLastModifiedMs() < existing.sourceLastModifiedMs) {
            return UpsertOutcome.STALE_IGNORED;
        }

        boolean unchanged = existing.matches(payload);
        if (unchanged && !existing.deleted) {
            return UpsertOutcome.UNCHANGED;
        }

        existing.applyPayload(payload, nowMs);
        return UpsertOutcome.UPDATED;
    }

    @Override
    public synchronized int markDeleted(String sourceDevice, Set<String> externalContactIds, long nowMs) {
        requireActiveTransaction();

        if (externalContactIds == null || externalContactIds.isEmpty()) {
            return 0;
        }

        Map<String, MutableContact> deviceContacts = contactsByDevice.get(sourceDevice);
        if (deviceContacts == null || deviceContacts.isEmpty()) {
            return 0;
        }

        int deleted = 0;
        for (String id : externalContactIds) {
            MutableContact contact = deviceContacts.get(id);
            if (contact != null && !contact.deleted) {
                contact.deleted = true;
                contact.localUpdatedMs = nowMs;
                deleted++;
            }
        }
        return deleted;
    }

    @Override
    public synchronized int markMissingDeleted(String sourceDevice, Set<String> liveContactIds, long nowMs) {
        requireActiveTransaction();

        Map<String, MutableContact> deviceContacts = contactsByDevice.get(sourceDevice);
        if (deviceContacts == null || deviceContacts.isEmpty()) {
            return 0;
        }

        Set<String> liveIds = liveContactIds == null ? Set.of() : new HashSet<>(liveContactIds);
        int deleted = 0;
        for (MutableContact contact : deviceContacts.values()) {
            if (!contact.deleted && !liveIds.contains(contact.externalContactId)) {
                contact.deleted = true;
                contact.localUpdatedMs = nowMs;
                deleted++;
            }
        }

        return deleted;
    }

    @Override
    public synchronized int purgeDeletedBefore(long cutoffMs) {
        int purged = 0;
        for (Map<String, MutableContact> contacts : contactsByDevice.values()) {
            List<String> idsToRemove = new ArrayList<>();
            for (MutableContact contact : contacts.values()) {
                if (contact.deleted && contact.localUpdatedMs < cutoffMs) {
                    idsToRemove.add(contact.externalContactId);
                }
            }
            for (String id : idsToRemove) {
                contacts.remove(id);
                purged++;
            }
        }
        return purged;
    }

    @Override
    public synchronized List<CachedContact> listActiveContacts(String sourceDevice, String namePrefix, int limit) {
        Map<String, MutableContact> deviceContacts = contactsByDevice.get(sourceDevice);
        if (deviceContacts == null || deviceContacts.isEmpty()) {
            return List.of();
        }

        String prefix = namePrefix == null ? null : namePrefix.toLowerCase(Locale.ROOT);
        List<CachedContact> result = new ArrayList<>();
        for (MutableContact contact : deviceContacts.values()) {
            if (contact.deleted) {
                continue;
            }
            if (prefix != null && !prefix.isEmpty()
                    && !contact.displayName.toLowerCase(Locale.ROOT).startsWith(prefix)) {
                continue;
            }
            result.add(contact.toCachedContact(sourceDevice));
        }

        result.sort(Comparator
                .comparing(CachedContact::getDisplayName, String.CASE_INSENSITIVE_ORDER)
                .thenComparing(CachedContact::getExternalContactId));

        if (limit <= 0 || result.size() <= limit) {
            return result;
        }
        return new ArrayList<>(result.subList(0, limit));
    }

    @Override
    public synchronized SyncState getSyncState(String sourceDevice) {
        return syncStateByDevice.get(sourceDevice);
    }

    @Override
    public synchronized void upsertSyncState(
            String sourceDevice,
            long lastFullSyncMs,
            String lastSyncToken,
            long lastSourceSyncSequence,
            int cacheSchemaVersion
    ) {
        requireActiveTransaction();
        syncStateByDevice.put(
                sourceDevice,
                new SyncState(
                        sourceDevice,
                        lastFullSyncMs,
                        lastSyncToken,
                        lastSourceSyncSequence,
                        cacheSchemaVersion
                )
        );
    }

    @Override
    public synchronized int countActiveContacts(String sourceDevice) {
        Map<String, MutableContact> deviceContacts = contactsByDevice.get(sourceDevice);
        if (deviceContacts == null || deviceContacts.isEmpty()) {
            return 0;
        }

        int count = 0;
        for (MutableContact contact : deviceContacts.values()) {
            if (!contact.deleted) {
                count++;
            }
        }
        return count;
    }

    private void commitTransaction() {
        synchronized (this) {
            if (!inTransaction) {
                return;
            }
            clearTransactionState();
        }
    }

    private void rollbackTransaction() {
        synchronized (this) {
            if (!inTransaction) {
                return;
            }
            contactsByDevice = txContactsSnapshot;
            syncStateByDevice = txSyncStateSnapshot;
            clearTransactionState();
        }
    }

    private void clearTransactionState() {
        inTransaction = false;
        txContactsSnapshot = null;
        txSyncStateSnapshot = null;
    }

    private void requireActiveTransaction() {
        if (!inTransaction) {
            throw new IllegalStateException("Write operation requires an active transaction");
        }
    }

    private static Map<String, Map<String, MutableContact>> deepCopyContacts(
            Map<String, Map<String, MutableContact>> source
    ) {
        Map<String, Map<String, MutableContact>> copy = new HashMap<>();
        for (Map.Entry<String, Map<String, MutableContact>> deviceEntry : source.entrySet()) {
            Map<String, MutableContact> byId = new LinkedHashMap<>();
            for (Map.Entry<String, MutableContact> contactEntry : deviceEntry.getValue().entrySet()) {
                byId.put(contactEntry.getKey(), contactEntry.getValue().copy());
            }
            copy.put(deviceEntry.getKey(), byId);
        }
        return copy;
    }

    private static final class Tx implements StoreTransaction {
        private final InMemoryContactsCacheStore store;
        private boolean committed;
        private boolean closed;

        private Tx(InMemoryContactsCacheStore store) {
            this.store = store;
        }

        @Override
        public void commit() {
            if (closed) {
                throw new IllegalStateException("Transaction already closed");
            }
            committed = true;
            store.commitTransaction();
            closed = true;
        }

        @Override
        public void close() {
            if (closed) {
                return;
            }
            if (!committed) {
                store.rollbackTransaction();
            }
            closed = true;
        }
    }

    private static final class MutableContact {
        private final String externalContactId;
        private String displayName;
        private List<String> phones;
        private List<String> emails;
        private String avatarEtag;
        private long sourceVersion;
        private long sourceLastModifiedMs;
        private long localUpdatedMs;
        private boolean deleted;

        private MutableContact(
                String externalContactId,
                String displayName,
                List<String> phones,
                List<String> emails,
                String avatarEtag,
                long sourceVersion,
                long sourceLastModifiedMs,
                long localUpdatedMs,
                boolean deleted
        ) {
            this.externalContactId = externalContactId;
            this.displayName = displayName;
            this.phones = new ArrayList<>(phones);
            this.emails = new ArrayList<>(emails);
            this.avatarEtag = avatarEtag;
            this.sourceVersion = sourceVersion;
            this.sourceLastModifiedMs = sourceLastModifiedMs;
            this.localUpdatedMs = localUpdatedMs;
            this.deleted = deleted;
        }

        private static MutableContact fromPayload(ContactPayload payload, long nowMs) {
            return new MutableContact(
                    payload.getExternalContactId(),
                    payload.getDisplayName(),
                    payload.getPhones(),
                    payload.getEmails(),
                    payload.getAvatarEtag(),
                    payload.getSourceVersion(),
                    payload.getSourceLastModifiedMs(),
                    nowMs,
                    false
            );
        }

        private boolean matches(ContactPayload payload) {
            return Objects.equals(displayName, payload.getDisplayName())
                    && Objects.equals(phones, payload.getPhones())
                    && Objects.equals(emails, payload.getEmails())
                    && Objects.equals(avatarEtag, payload.getAvatarEtag())
                    && sourceVersion == payload.getSourceVersion()
                    && sourceLastModifiedMs == payload.getSourceLastModifiedMs();
        }

        private void applyPayload(ContactPayload payload, long nowMs) {
            this.displayName = payload.getDisplayName();
            this.phones = new ArrayList<>(payload.getPhones());
            this.emails = new ArrayList<>(payload.getEmails());
            this.avatarEtag = payload.getAvatarEtag();
            this.sourceVersion = payload.getSourceVersion();
            this.sourceLastModifiedMs = payload.getSourceLastModifiedMs();
            this.localUpdatedMs = nowMs;
            this.deleted = false;
        }

        private MutableContact copy() {
            return new MutableContact(
                    externalContactId,
                    displayName,
                    phones,
                    emails,
                    avatarEtag,
                    sourceVersion,
                    sourceLastModifiedMs,
                    localUpdatedMs,
                    deleted
            );
        }

        private CachedContact toCachedContact(String sourceDevice) {
            return new CachedContact(
                    sourceDevice,
                    externalContactId,
                    displayName,
                    phones,
                    emails,
                    avatarEtag,
                    sourceVersion,
                    sourceLastModifiedMs,
                    localUpdatedMs
            );
        }
    }
}
