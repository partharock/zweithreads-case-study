package com.autotech.aaos.contactscache.core.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

public final class CachedContact {
    private final String sourceDevice;
    private final String externalContactId;
    private final String displayName;
    private final List<String> phones;
    private final List<String> emails;
    private final String avatarEtag;
    private final long sourceVersion;
    private final long sourceLastModifiedMs;
    private final long localUpdatedMs;

    public CachedContact(
            String sourceDevice,
            String externalContactId,
            String displayName,
            List<String> phones,
            List<String> emails,
            String avatarEtag,
            long sourceVersion,
            long sourceLastModifiedMs,
            long localUpdatedMs
    ) {
        this.sourceDevice = Objects.requireNonNull(sourceDevice, "sourceDevice");
        this.externalContactId = Objects.requireNonNull(externalContactId, "externalContactId");
        this.displayName = Objects.requireNonNull(displayName, "displayName");
        this.phones = Collections.unmodifiableList(new ArrayList<>(phones == null ? List.of() : phones));
        this.emails = Collections.unmodifiableList(new ArrayList<>(emails == null ? List.of() : emails));
        this.avatarEtag = avatarEtag;
        this.sourceVersion = sourceVersion;
        this.sourceLastModifiedMs = sourceLastModifiedMs;
        this.localUpdatedMs = localUpdatedMs;
    }

    public String getSourceDevice() {
        return sourceDevice;
    }

    public String getExternalContactId() {
        return externalContactId;
    }

    public String getDisplayName() {
        return displayName;
    }

    public List<String> getPhones() {
        return phones;
    }

    public List<String> getEmails() {
        return emails;
    }

    public String getAvatarEtag() {
        return avatarEtag;
    }

    public long getSourceVersion() {
        return sourceVersion;
    }

    public long getSourceLastModifiedMs() {
        return sourceLastModifiedMs;
    }

    public long getLocalUpdatedMs() {
        return localUpdatedMs;
    }
}
