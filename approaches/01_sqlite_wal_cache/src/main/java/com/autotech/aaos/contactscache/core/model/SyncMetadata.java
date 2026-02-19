package com.autotech.aaos.contactscache.core.model;

public final class SyncMetadata {
    private final String syncToken;
    private final long sourceSyncSequence;
    private final boolean completeSnapshot;
    private final boolean allowSequenceRegression;

    public SyncMetadata(
            String syncToken,
            long sourceSyncSequence,
            boolean completeSnapshot,
            boolean allowSequenceRegression
    ) {
        this.syncToken = syncToken;
        this.sourceSyncSequence = sourceSyncSequence;
        this.completeSnapshot = completeSnapshot;
        this.allowSequenceRegression = allowSequenceRegression;
    }

    public static SyncMetadata full(String syncToken, long sourceSyncSequence, boolean completeSnapshot) {
        return new SyncMetadata(syncToken, sourceSyncSequence, completeSnapshot, false);
    }

    public static SyncMetadata delta(String syncToken, long sourceSyncSequence) {
        return new SyncMetadata(syncToken, sourceSyncSequence, false, false);
    }

    public String getSyncToken() {
        return syncToken;
    }

    public long getSourceSyncSequence() {
        return sourceSyncSequence;
    }

    public boolean isCompleteSnapshot() {
        return completeSnapshot;
    }

    public boolean isAllowSequenceRegression() {
        return allowSequenceRegression;
    }
}
