package com.autotech.aaos.contactscache.core.util;

public final class PiiRedaction {
    private PiiRedaction() {
    }

    public static String redactPhone(String phone) {
        if (phone == null || phone.isBlank()) {
            return "****";
        }
        int digits = 0;
        for (int i = 0; i < phone.length(); i++) {
            if (Character.isDigit(phone.charAt(i))) {
                digits++;
            }
        }
        if (digits <= 4) {
            return "****";
        }
        return "*".repeat(digits - 4) + lastDigits(phone, 4);
    }

    private static String lastDigits(String value, int count) {
        StringBuilder digits = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (Character.isDigit(c)) {
                digits.append(c);
            }
        }
        if (digits.length() <= count) {
            return digits.toString();
        }
        return digits.substring(digits.length() - count);
    }
}
