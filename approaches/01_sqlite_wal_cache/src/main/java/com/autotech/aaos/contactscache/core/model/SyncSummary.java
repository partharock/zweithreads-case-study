package com.autotech.aaos.contactscache.core.model;

public final class SyncSummary {
    private final int inserted;
    private final int updated;
    private final int unchanged;
    private final int deleted;
    private final int staleIgnored;
    private final int invalidDropped;
    private final boolean partialSnapshot;

    public SyncSummary(
            int inserted,
            int updated,
            int unchanged,
            int deleted,
            int staleIgnored,
            int invalidDropped,
            boolean partialSnapshot
    ) {
        this.inserted = inserted;
        this.updated = updated;
        this.unchanged = unchanged;
        this.deleted = deleted;
        this.staleIgnored = staleIgnored;
        this.invalidDropped = invalidDropped;
        this.partialSnapshot = partialSnapshot;
    }

    public int getInserted() {
        return inserted;
    }

    public int getUpdated() {
        return updated;
    }

    public int getUnchanged() {
        return unchanged;
    }

    public int getDeleted() {
        return deleted;
    }

    public int getStaleIgnored() {
        return staleIgnored;
    }

    public int getInvalidDropped() {
        return invalidDropped;
    }

    public boolean isPartialSnapshot() {
        return partialSnapshot;
    }

    @Override
    public String toString() {
        return "SyncSummary{"
                + "inserted=" + inserted
                + ", updated=" + updated
                + ", unchanged=" + unchanged
                + ", deleted=" + deleted
                + ", staleIgnored=" + staleIgnored
                + ", invalidDropped=" + invalidDropped
                + ", partialSnapshot=" + partialSnapshot
                + '}';
    }
}
