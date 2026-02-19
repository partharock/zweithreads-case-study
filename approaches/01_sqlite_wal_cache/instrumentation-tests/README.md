# Android Instrumentation Test Scaffold (Option 2)

This folder provides Android runtime integration tests for the AAOS cache implementation.

## Scope covered

- Real SQLite persistence tests on Android runtime.
- Full/delta sync integration behavior.
- Sequence regression rejection.
- DB migration (`v1 -> v2`) and schema/index verification.
- UID access enforcement tests.

## Files

- `build.gradle.kts`
- `settings.gradle.kts`
- `gradle.properties`
- `src/main/AndroidManifest.xml`
- `src/androidTest/java/com/autotech/aaos/contactscache/integration/ContactsCacheStoreIntegrationTest.java`
- `src/androidTest/java/com/autotech/aaos/contactscache/integration/ContactsCacheDatabaseMigrationTest.java`
- `src/androidTest/java/com/autotech/aaos/contactscache/integration/ContactsCacheAccessEnforcerTest.java`
- `Android.bp.sample` (AOSP module template)
- `Android.bp` (actual AOSP module for this repo)
- `AndroidTest.template.xml` (Tradefed template)
- `AndroidTest.xml` (actual Tradefed config for this repo)

## How to run (Gradle Android project)

```bash
cd approaches/01_sqlite_wal_cache/instrumentation-tests
gradle connectedDebugAndroidTest
```

## How to run in AAOS/AOSP CI

1. Move the test sources under your AOSP test module path.
2. Use `Android.bp` + `AndroidTest.xml` as the concrete baseline.
3. Keep `Android.bp.sample` + `AndroidTest.template.xml` for branch-specific variants.
4. Run with `atest ContactsCacheIntegrationTests` on emulator/device targets.

## Notes

- These are instrumentation tests; they must run on Android runtime (emulator or device).
- This repo environment may not include working Android SDK/Gradle runtime, so local execution can be limited.
