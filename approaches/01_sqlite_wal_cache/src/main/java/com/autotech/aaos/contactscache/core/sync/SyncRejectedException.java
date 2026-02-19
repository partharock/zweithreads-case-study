package com.autotech.aaos.contactscache.core.sync;

public final class SyncRejectedException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    public SyncRejectedException(String message) {
        super(message);
    }
}
