package com.autotech.aaos.contactscache.core.model;

public final class CacheLimits {
    private final int maxContactsPerDevice;
    private final int maxPhonesPerContact;
    private final int maxEmailsPerContact;
    private final int maxDisplayNameChars;
    private final int maxPhoneChars;
    private final int maxEmailChars;
    private final int maxSourceDeviceChars;
    private final int maxExternalIdChars;

    public CacheLimits(
            int maxContactsPerDevice,
            int maxPhonesPerContact,
            int maxEmailsPerContact,
            int maxDisplayNameChars,
            int maxPhoneChars,
            int maxEmailChars,
            int maxSourceDeviceChars,
            int maxExternalIdChars
    ) {
        this.maxContactsPerDevice = maxContactsPerDevice;
        this.maxPhonesPerContact = maxPhonesPerContact;
        this.maxEmailsPerContact = maxEmailsPerContact;
        this.maxDisplayNameChars = maxDisplayNameChars;
        this.maxPhoneChars = maxPhoneChars;
        this.maxEmailChars = maxEmailChars;
        this.maxSourceDeviceChars = maxSourceDeviceChars;
        this.maxExternalIdChars = maxExternalIdChars;
    }

    public static CacheLimits productionDefaults() {
        return new CacheLimits(
                50_000,
                20,
                20,
                256,
                64,
                320,
                128,
                128
        );
    }

    public int getMaxContactsPerDevice() {
        return maxContactsPerDevice;
    }

    public int getMaxPhonesPerContact() {
        return maxPhonesPerContact;
    }

    public int getMaxEmailsPerContact() {
        return maxEmailsPerContact;
    }

    public int getMaxDisplayNameChars() {
        return maxDisplayNameChars;
    }

    public int getMaxPhoneChars() {
        return maxPhoneChars;
    }

    public int getMaxEmailChars() {
        return maxEmailChars;
    }

    public int getMaxSourceDeviceChars() {
        return maxSourceDeviceChars;
    }

    public int getMaxExternalIdChars() {
        return maxExternalIdChars;
    }
}
