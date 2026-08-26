#!/bin/bash
# Setup script to install Android build prerequisites
# Run this before the first build
set -e

echo "========================================="
echo "  Installing Android Build Prerequisites"
echo "========================================="
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "ERROR: Homebrew not found. Install from https://brew.sh"
    exit 1
fi

echo "Installing build tools..."
brew install autoconf automake libtool pkg-config cmake

echo ""
echo "Installing JDK 17 (required by python-for-android)..."
brew install openjdk@17

echo ""
echo "Setting up environment..."
echo 'export JAVA_HOME=$(/usr/libexec/java_home -v 17)' >> ~/.zshrc
export JAVA_HOME=$(/usr/libexec/java_home -v 17)

echo ""
echo "========================================="
echo "  Prerequisites installed!"
echo "========================================="
echo ""
echo "Now run: cd mobile && ./build.sh"