package com.autotech.aaos.contactscache.core.util;

import com.autotech.aaos.contactscache.core.model.CacheLimits;
import com.autotech.aaos.contactscache.core.model.ContactPayload;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public final class ContactNormalizer {
    private ContactNormalizer() {
    }

    public static ContactPayload normalize(ContactPayload input, CacheLimits limits) {
        if (input == null) {
            return null;
        }

        String externalId = trimToNull(input.getExternalContactId());
        if (externalId == null) {
            return null;
        }
        externalId = truncate(externalId, limits.getMaxExternalIdChars());

        String displayName = trimToNull(input.getDisplayName());
        if (displayName == null) {
            displayName = "Unknown";
        }
        displayName = truncate(displayName, limits.getMaxDisplayNameChars());

        List<String> phones = normalizePhones(input.getPhones(), limits);
        List<String> emails = normalizeEmails(input.getEmails(), limits);

        String avatar = trimToNull(input.getAvatarEtag());
        if (avatar != null && avatar.length() > 128) {
            avatar = avatar.substring(0, 128);
        }

        long sourceVersion = Math.max(0L, input.getSourceVersion());
        long sourceLastModifiedMs = Math.max(0L, input.getSourceLastModifiedMs());

        return new ContactPayload(
                externalId,
                displayName,
                phones,
                emails,
                avatar,
                sourceVersion,
                sourceLastModifiedMs
        );
    }

    public static String normalizeSourceDevice(String sourceDevice, CacheLimits limits) {
        String normalized = trimToNull(sourceDevice);
        if (normalized == null) {
            throw new IllegalArgumentException("sourceDevice must be non-empty");
        }
        return truncate(normalized, limits.getMaxSourceDeviceChars());
    }

    private static List<String> normalizePhones(List<String> rawPhones, CacheLimits limits) {
        if (rawPhones == null || rawPhones.isEmpty()) {
            return List.of();
        }
        Set<String> deduped = new LinkedHashSet<>();
        for (String raw : rawPhones) {
            String normalized = normalizePhone(raw);
            if (normalized == null) {
                continue;
            }
            if (normalized.length() > limits.getMaxPhoneChars()) {
                normalized = normalized.substring(0, limits.getMaxPhoneChars());
            }
            deduped.add(normalized);
            if (deduped.size() >= limits.getMaxPhonesPerContact()) {
                break;
            }
        }
        return new ArrayList<>(deduped);
    }

    private static List<String> normalizeEmails(List<String> rawEmails, CacheLimits limits) {
        if (rawEmails == null || rawEmails.isEmpty()) {
            return List.of();
        }
        Set<String> deduped = new LinkedHashSet<>();
        for (String raw : rawEmails) {
            String normalized = trimToNull(raw);
            if (normalized == null) {
                continue;
            }
            normalized = normalized.toLowerCase(Locale.ROOT);
            if (!normalized.contains("@")) {
                continue;
            }
            if (normalized.length() > limits.getMaxEmailChars()) {
                normalized = normalized.substring(0, limits.getMaxEmailChars());
            }
            deduped.add(normalized);
            if (deduped.size() >= limits.getMaxEmailsPerContact()) {
                break;
            }
        }
        return new ArrayList<>(deduped);
    }

    private static String normalizePhone(String rawPhone) {
        String trimmed = trimToNull(rawPhone);
        if (trimmed == null) {
            return null;
        }

        StringBuilder sb = new StringBuilder(trimmed.length());
        boolean plusUsed = false;
        int digits = 0;
        for (int i = 0; i < trimmed.length(); i++) {
            char ch = trimmed.charAt(i);
            if (Character.isDigit(ch)) {
                sb.append(ch);
                digits++;
                continue;
            }
            if (ch == '+' && !plusUsed && sb.length() == 0) {
                sb.append(ch);
                plusUsed = true;
            }
        }

        if (digits == 0) {
            return null;
        }

        return sb.toString();
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static String truncate(String value, int maxChars) {
        if (value.length() <= maxChars) {
            return value;
        }
        return value.substring(0, maxChars);
    }
}
