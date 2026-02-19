package com.autotech.aaos.contactscache.approach2;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Lightweight prototype-only implementation.
 *
 * Not recommended for production AAOS contact cache because it rewrites full snapshots
 * and lacks transactional guarantees.
 */
public final class JsonSnapshotCache {
    private final Path rootDir;

    public JsonSnapshotCache(Path rootDir) {
        this.rootDir = Objects.requireNonNull(rootDir, "rootDir");
    }

    public void writeSnapshot(String sourceDevice, List<Map<String, String>> contacts) throws IOException {
        Files.createDirectories(rootDir);
        Path out = rootDir.resolve(safeName(sourceDevice) + ".json");

        StringBuilder json = new StringBuilder();
        json.append("{\n  \"sourceDevice\": \"").append(escape(sourceDevice)).append("\",\n");
        json.append("  \"contacts\": [\n");
        for (int i = 0; i < contacts.size(); i++) {
            Map<String, String> contact = contacts.get(i);
            json.append("    {");
            int fieldIndex = 0;
            for (Map.Entry<String, String> entry : contact.entrySet()) {
                if (fieldIndex++ > 0) {
                    json.append(", ");
                }
                json.append("\"").append(escape(entry.getKey())).append("\": ");
                json.append("\"").append(escape(entry.getValue())).append("\"");
            }
            json.append("}");
            if (i < contacts.size() - 1) {
                json.append(",");
            }
            json.append("\n");
        }
        json.append("  ]\n}\n");

        Files.writeString(out, json.toString(), StandardCharsets.UTF_8);
    }

    private static String safeName(String sourceDevice) {
        return sourceDevice.replace('/', '_').replace(':', '_');
    }

    private static String escape(String input) {
        return input.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
