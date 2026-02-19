package com.autotech.aaos.contactscache.core.model;

public final class SyncState {
    private final String sourceDevice;
    private final long lastFullSyncMs;
    private final String lastSyncToken;
    private final long lastSourceSyncSequence;
    private final int cacheSchemaVersion;

    public SyncState(
            String sourceDevice,
            long lastFullSyncMs,
            String lastSyncToken,
            long lastSourceSyncSequence,
            int cacheSchemaVersion
    ) {
        this.sourceDevice = sourceDevice;
        this.lastFullSyncMs = lastFullSyncMs;
        this.lastSyncToken = lastSyncToken;
        this.lastSourceSyncSequence = lastSourceSyncSequence;
        this.cacheSchemaVersion = cacheSchemaVersion;
    }

    public String getSourceDevice() {
        return sourceDevice;
    }

    public long getLastFullSyncMs() {
        return lastFullSyncMs;
    }

    public String getLastSyncToken() {
        return lastSyncToken;
    }

    public long getLastSourceSyncSequence() {
        return lastSourceSyncSequence;
    }

    public int getCacheSchemaVersion() {
        return cacheSchemaVersion;
    }
}
