package com.autotech.aaos.contactscache.android;

import android.os.Binder;

import java.util.Set;

public final class ContactsCacheAccessEnforcer {
    public interface CallingUidProvider {
        int getCallingUid();
    }

    private final Set<Integer> allowedReadUids;
    private final Set<Integer> allowedWriteUids;
    private final CallingUidProvider callingUidProvider;

    public ContactsCacheAccessEnforcer(Set<Integer> allowedReadUids, Set<Integer> allowedWriteUids) {
        this(allowedReadUids, allowedWriteUids, Binder::getCallingUid);
    }

    public ContactsCacheAccessEnforcer(
            Set<Integer> allowedReadUids,
            Set<Integer> allowedWriteUids,
            CallingUidProvider callingUidProvider
    ) {
        this.allowedReadUids = Set.copyOf(allowedReadUids);
        this.allowedWriteUids = Set.copyOf(allowedWriteUids);
        this.callingUidProvider = callingUidProvider;
    }

    public void enforceReadAccess() {
        int uid = callingUidProvider.getCallingUid();
        if (!allowedReadUids.contains(uid)) {
            throw new SecurityException("UID " + uid + " is not authorized to read synced contacts cache");
        }
    }

    public void enforceWriteAccess() {
        int uid = callingUidProvider.getCallingUid();
        if (!allowedWriteUids.contains(uid)) {
            throw new SecurityException("UID " + uid + " is not authorized to write synced contacts cache");
        }
    }
}
