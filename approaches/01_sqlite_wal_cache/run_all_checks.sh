#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTRUMENTATION_DIR="$ROOT_DIR/instrumentation-tests"
ANDROID_SDK_ROOT_DEFAULT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"
ANDROID_COMPILE_SDK="${ANDROID_COMPILE_SDK:-34}"
ANDROID_JAR="$ANDROID_SDK_ROOT_DEFAULT/platforms/android-$ANDROID_COMPILE_SDK/android.jar"

echo "==> 1/3 Running JVM core tests"
"$ROOT_DIR/run_jvm_tests.sh"

echo "==> 2/3 Compiling Android sources against android-$ANDROID_COMPILE_SDK"
if [[ ! -f "$ANDROID_JAR" ]]; then
    echo "ERROR: android.jar not found at: $ANDROID_JAR"
    echo "Set ANDROID_SDK_ROOT and/or ANDROID_COMPILE_SDK."
    exit 1
fi

BUILD_DIR="$ROOT_DIR/build/android-compile-check"
CLASSES_DIR="$BUILD_DIR/classes"
rm -rf "$BUILD_DIR"
mkdir -p "$CLASSES_DIR"
find "$ROOT_DIR/src/main/java" -name '*.java' | sort > "$BUILD_DIR/sources.txt"
javac -Xlint:all -cp "$ANDROID_JAR" -d "$CLASSES_DIR" @"$BUILD_DIR/sources.txt"
echo "Android compile check passed."

if [[ "${RUN_CONNECTED_TESTS:-0}" != "1" ]]; then
    echo "==> 3/3 Skipping connected instrumentation tests (set RUN_CONNECTED_TESTS=1 to enable)"
    exit 0
fi

if ! command -v adb >/dev/null 2>&1; then
    echo "ERROR: adb command not found."
    exit 1
fi

DEVICE_COUNT="$(adb devices | awk 'NR > 1 && $2 == "device" {count++} END {print count + 0}')"
if [[ "$DEVICE_COUNT" -eq 0 ]]; then
    echo "ERROR: No connected Android/AAOS device detected."
    echo "Connect a device or start an emulator, then rerun with RUN_CONNECTED_TESTS=1."
    exit 1
fi

echo "==> 3/3 Running connected instrumentation tests"
(
    cd "$INSTRUMENTATION_DIR"
    ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT_DEFAULT" \
    GRADLE_USER_HOME="${GRADLE_USER_HOME:-$INSTRUMENTATION_DIR/.gradle-home}" \
    gradle connectedDebugAndroidTest --no-daemon
)
