package com.autotech.aaos.contactscache.approach3;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Objects;

/**
 * Event-log persistence alternative. Useful for audit-heavy systems,
 * but it is not the best default for AAOS contact lookup latency.
 */
public final class EventLogCache {
    private final Path rootDir;

    public EventLogCache(Path rootDir) {
        this.rootDir = Objects.requireNonNull(rootDir, "rootDir");
    }

    public void appendUpsert(String sourceDevice, String externalContactId, String payloadJson) throws IOException {
        appendEvent(sourceDevice, "upsert", externalContactId, payloadJson);
    }

    public void appendDelete(String sourceDevice, String externalContactId) throws IOException {
        appendEvent(sourceDevice, "delete", externalContactId, "{}");
    }

    private void appendEvent(String sourceDevice, String type, String externalContactId, String payloadJson)
            throws IOException {
        Files.createDirectories(rootDir);
        Path file = rootDir.resolve(safeName(sourceDevice) + ".events.ndjson");
        String event = "{\"type\":\"" + escape(type)
                + "\",\"externalContactId\":\"" + escape(externalContactId)
                + "\",\"payload\":" + payloadJson
                + "}" + System.lineSeparator();

        Files.writeString(
                file,
                event,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,
                StandardOpenOption.APPEND
        );
    }

    private static String safeName(String sourceDevice) {
        return sourceDevice.replace('/', '_').replace(':', '_');
    }

    private static String escape(String input) {
        return input.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
