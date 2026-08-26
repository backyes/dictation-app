#!/bin/bash
# Build script for Android APK
# Usage: ./build.sh [debug|release]
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_MODE="${1:-debug}"

echo "========================================="
echo "  Dictation Practice - Android APK Build"
echo "========================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Build mode: $BUILD_MODE"
echo ""

# Check buildozer
if ! command -v buildozer &> /dev/null; then
    echo "ERROR: buildozer not found. Install with: pip install buildozer"
    exit 1
fi

echo "Buildozer version: $(buildozer --version)"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
MISSING=0

check_cmd() {
    if command -v "$1" &> /dev/null; then
        echo "  ✓ $1"
    else
        echo "  ✗ $1 (missing)"
        MISSING=1
    fi
}

check_cmd autoconf
check_cmd automake
check_cmd libtool
check_cmd pkg-config
check_cmd cmake
check_cmd javac
check_cmd git
check_cmd cython

# Check Java version
JAVA_VER=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | cut -d'.' -f1)
if [ "$JAVA_VER" = "17" ] || [ "$JAVA_VER" = "11" ]; then
    echo "  ✓ java (version $JAVA_VER)"
else
    echo "  ⚠ java version $JAVA_VER (recommended: 17 or 11)"
fi

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "ERROR: Missing prerequisites. Run ./setup.sh first."
    exit 1
fi

echo ""

# Navigate to mobile directory for build
cd "$SCRIPT_DIR"

# Initialize buildozer.spec if needed
if [ ! -f "buildozer.spec" ]; then
    echo "ERROR: buildozer.spec not found in $SCRIPT_DIR"
    exit 1
fi

echo "Using buildozer.spec: $(pwd)/buildozer.spec"
echo ""

# Build the APK
echo "Starting buildozer android $BUILD_MODE..."
echo "This may take a long time on first run (downloading SDK/NDK)."
echo ""

buildozer android "$BUILD_MODE" 2>&1

BUILD_EXIT=$?

if [ $BUILD_EXIT -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "  BUILD SUCCESSFUL!"
    echo "========================================="
    echo ""
    
    # Find the APK
    APK_PATH=$(find "$SCRIPT_DIR/bin" -name "*.apk" -type f 2>/dev/null | head -1)
    
    if [ -n "$APK_PATH" ]; then
        APK_SIZE=$(du -h "$APK_PATH" | cut -f1)
        echo "APK: $APK_PATH"
        echo "Size: $APK_SIZE"
        echo ""
        echo "Install with: adb install \"$APK_PATH\""
    else
        echo "APK location: $SCRIPT_DIR/bin/"
        ls -la "$SCRIPT_DIR/bin/" 2>/dev/null || true
    fi
else
    echo ""
    echo "========================================="
    echo "  BUILD FAILED (exit code: $BUILD_EXIT)"
    echo "========================================="
    echo ""
    echo "Check the output above for errors."
    echo "Common issues:"
    echo "  - Missing Android SDK/NDK (buildozer will download on first run)"
    echo "  - Missing dependencies in requirements"
    echo "  - Python import errors in main.py"
    exit $BUILD_EXIT
fi