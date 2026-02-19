#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$ROOT_DIR/build/jvm-tests"
CLASSES_DIR="$BUILD_DIR/classes"

rm -rf "$BUILD_DIR"
mkdir -p "$CLASSES_DIR"

MAIN_SOURCES=$(find "$ROOT_DIR/src/main/java" -name '*.java' ! -path '*/android/*' | tr '\n' ' ')
TEST_SOURCES=$(find "$ROOT_DIR/src/test/java" -name '*.java' | tr '\n' ' ')

javac -Xlint:all -Werror -d "$CLASSES_DIR" $MAIN_SOURCES $TEST_SOURCES

java -cp "$CLASSES_DIR" com.autotech.aaos.contactscache.core.ContactSyncEngineTestRunner
