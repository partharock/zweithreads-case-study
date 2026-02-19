# Approach 2: JSON Snapshot Cache (Java)

## Summary

Stores one full JSON snapshot file per source device.

## Code

- `src/main/java/com/autotech/aaos/contactscache/approach2/JsonSnapshotCache.java`

## Pros

- Very simple implementation.
- Human-readable snapshots.

## Cons

- Full rewrite on every sync.
- No transactional safety for large payload writes.
- Weak query performance for contact lookup/search.

## Verdict

Useful only for prototypes. Not recommended for production AAOS contact caching.
