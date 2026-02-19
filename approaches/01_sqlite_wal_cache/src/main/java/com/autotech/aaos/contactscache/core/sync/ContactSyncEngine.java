package com.autotech.aaos.contactscache.core.sync;

import com.autotech.aaos.contactscache.core.model.CacheLimits;
import com.autotech.aaos.contactscache.core.model.ContactPayload;
import com.autotech.aaos.contactscache.core.model.SyncMetadata;
import com.autotech.aaos.contactscache.core.model.SyncState;
import com.autotech.aaos.contactscache.core.model.SyncSummary;
import com.autotech.aaos.contactscache.core.model.UpsertOutcome;
import com.autotech.aaos.contactscache.core.store.ContactsCacheStore;
import com.autotech.aaos.contactscache.core.store.StoreTransaction;
import com.autotech.aaos.contactscache.core.util.Clock;
import com.autotech.aaos.contactscache.core.util.ContactNormalizer;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class ContactSyncEngine {
    private static final int CACHE_SCHEMA_VERSION = 1;

    private final ContactsCacheStore store;
    private final CacheLimits limits;
    private final Clock clock;

    public ContactSyncEngine(ContactsCacheStore store) {
        this(store, CacheLimits.productionDefaults(), Clock.SYSTEM);
    }

    public ContactSyncEngine(ContactsCacheStore store, CacheLimits limits, Clock clock) {
        this.store = store;
        this.limits = limits;
        this.clock = clock;
    }

    public SyncSummary applyFullSync(
            String sourceDevice,
            List<ContactPayload> incomingContacts,
            SyncMetadata metadata
    ) {
        String normalizedSource = ContactNormalizer.normalizeSourceDevice(sourceDevice, limits);
        SyncMetadata resolvedMetadata = metadata == null
                ? SyncMetadata.full(null, 0L, false)
                : metadata;

        NormalizationResult normalized = normalizeAndDedupe(incomingContacts);
        ensureDeviceCapacity(normalized.normalizedContacts.size());

        long nowMs = clock.nowMs();

        int inserted = 0;
        int updated = 0;
        int unchanged = 0;
        int staleIgnored = 0;

        try (StoreTransaction tx = store.beginTransaction()) {
            ensureSyncSequenceMonotonic(normalizedSource, resolvedMetadata);

            Set<String> liveIds = new LinkedHashSet<>();
            for (ContactPayload payload : normalized.normalizedContacts) {
                liveIds.add(payload.getExternalContactId());
                UpsertOutcome outcome = store.upsertContact(normalizedSource, payload, nowMs);
                if (outcome == UpsertOutcome.INSERTED) {
                    inserted++;
                } else if (outcome == UpsertOutcome.UPDATED) {
                    updated++;
                } else if (outcome == UpsertOutcome.UNCHANGED) {
                    unchanged++;
                } else if (outcome == UpsertOutcome.STALE_IGNORED) {
                    staleIgnored++;
                }
            }

            int deleted = 0;
            if (resolvedMetadata.isCompleteSnapshot()) {
                deleted = store.markMissingDeleted(normalizedSource, liveIds, nowMs);
            }

            store.upsertSyncState(
                    normalizedSource,
                    nowMs,
                    resolvedMetadata.getSyncToken(),
                    resolvedMetadata.getSourceSyncSequence(),
                    CACHE_SCHEMA_VERSION
            );
            tx.commit();

            return new SyncSummary(
                    inserted,
                    updated,
                    unchanged,
                    deleted,
                    staleIgnored,
                    normalized.invalidDropped,
                    !resolvedMetadata.isCompleteSnapshot()
            );
        }
    }

    public SyncSummary applyDeltaSync(
            String sourceDevice,
            List<ContactPayload> upserts,
            List<String> deletions,
            SyncMetadata metadata
    ) {
        String normalizedSource = ContactNormalizer.normalizeSourceDevice(sourceDevice, limits);
        SyncMetadata resolvedMetadata = metadata == null
                ? SyncMetadata.delta(null, 0L)
                : metadata;

        NormalizationResult normalizedUpserts = normalizeAndDedupe(upserts);
        ensureDeviceCapacity(normalizedUpserts.normalizedContacts.size() + store.countActiveContacts(normalizedSource));

        Set<String> deletionIds = normalizeDeletionIds(deletions);
        for (ContactPayload payload : normalizedUpserts.normalizedContacts) {
            deletionIds.remove(payload.getExternalContactId());
        }

        long nowMs = clock.nowMs();

        int inserted = 0;
        int updated = 0;
        int unchanged = 0;
        int staleIgnored = 0;

        try (StoreTransaction tx = store.beginTransaction()) {
            ensureSyncSequenceMonotonic(normalizedSource, resolvedMetadata);

            for (ContactPayload payload : normalizedUpserts.normalizedContacts) {
                UpsertOutcome outcome = store.upsertContact(normalizedSource, payload, nowMs);
                if (outcome == UpsertOutcome.INSERTED) {
                    inserted++;
                } else if (outcome == UpsertOutcome.UPDATED) {
                    updated++;
                } else if (outcome == UpsertOutcome.UNCHANGED) {
                    unchanged++;
                } else if (outcome == UpsertOutcome.STALE_IGNORED) {
                    staleIgnored++;
                }
            }

            int deleted = store.markDeleted(normalizedSource, deletionIds, nowMs);
            store.upsertSyncState(
                    normalizedSource,
                    nowMs,
                    resolvedMetadata.getSyncToken(),
                    resolvedMetadata.getSourceSyncSequence(),
                    CACHE_SCHEMA_VERSION
            );
            tx.commit();

            return new SyncSummary(
                    inserted,
                    updated,
                    unchanged,
                    deleted,
                    staleIgnored,
                    normalizedUpserts.invalidDropped,
                    true
            );
        }
    }

    private void ensureSyncSequenceMonotonic(String sourceDevice, SyncMetadata metadata) {
        if (metadata.getSourceSyncSequence() <= 0L) {
            return;
        }

        SyncState syncState = store.getSyncState(sourceDevice);
        if (syncState == null) {
            return;
        }

        long previous = syncState.getLastSourceSyncSequence();
        long incoming = metadata.getSourceSyncSequence();
        if (!metadata.isAllowSequenceRegression() && incoming < previous) {
            throw new SyncRejectedException(
                    "Rejected sync for sourceDevice=" + sourceDevice
                            + " due to sequence regression. incoming=" + incoming
                            + " previous=" + previous
            );
        }
    }

    private void ensureDeviceCapacity(int requestedContactCount) {
        if (requestedContactCount > limits.getMaxContactsPerDevice()) {
            throw new SyncRejectedException(
                    "Contact count exceeds maxContactsPerDevice=" + limits.getMaxContactsPerDevice()
            );
        }
    }

    private NormalizationResult normalizeAndDedupe(List<ContactPayload> incomingContacts) {
        Map<String, ContactPayload> deduped = new LinkedHashMap<>();
        int invalidDropped = 0;

        List<ContactPayload> inputs = incomingContacts == null ? List.of() : incomingContacts;
        for (ContactPayload raw : inputs) {
            ContactPayload normalized = ContactNormalizer.normalize(raw, limits);
            if (normalized == null) {
                invalidDropped++;
                continue;
            }

            ContactPayload existing = deduped.get(normalized.getExternalContactId());
            if (existing == null || isPreferred(normalized, existing)) {
                deduped.put(normalized.getExternalContactId(), normalized);
            }
        }

        return new NormalizationResult(new ArrayList<>(deduped.values()), invalidDropped);
    }

    private Set<String> normalizeDeletionIds(List<String> deletions) {
        Set<String> normalized = new LinkedHashSet<>();
        if (deletions == null || deletions.isEmpty()) {
            return normalized;
        }
        for (String raw : deletions) {
            if (raw == null) {
                continue;
            }
            String trimmed = raw.trim();
            if (!trimmed.isEmpty()) {
                normalized.add(trimmed.substring(0, Math.min(trimmed.length(), limits.getMaxExternalIdChars())));
            }
        }
        return normalized;
    }

    private boolean isPreferred(ContactPayload candidate, ContactPayload existing) {
        if (candidate.getSourceVersion() > existing.getSourceVersion()) {
            return true;
        }
        if (candidate.getSourceVersion() < existing.getSourceVersion()) {
            return false;
        }
        return candidate.getSourceLastModifiedMs() >= existing.getSourceLastModifiedMs();
    }

    private static final class NormalizationResult {
        private final List<ContactPayload> normalizedContacts;
        private final int invalidDropped;

        private NormalizationResult(List<ContactPayload> normalizedContacts, int invalidDropped) {
            this.normalizedContacts = normalizedContacts;
            this.invalidDropped = invalidDropped;
        }
    }
}
