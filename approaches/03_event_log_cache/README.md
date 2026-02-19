# Approach 3: Append-Only Event Log Cache (Java)

## Summary

Persists contact mutations as append-only events (`ndjson`) and reconstructs state by replay.

## Code

- `src/main/java/com/autotech/aaos/contactscache/approach3/EventLogCache.java`

## Pros

- Strong auditability.
- Sequential writes are durable.

## Cons

- Read latency grows unless compaction is aggressive.
- More operational complexity than SQLite table cache.

## Verdict

Appropriate for audit-first systems. For AAOS contact lookup performance, SQLite table cache is the better default.
