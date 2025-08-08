#!/bin/bash

# MITA Flutter App Launch Script
# This script ensures the app launches successfully on the Android emulator

echo "🚀 Launching MITA Flutter App..."

# Check if Flutter is available
if ! command -v flutter &> /dev/null; then
    echo "❌ Flutter is not installed or not in PATH"
    exit 1
fi

# Check if emulator is running
if ! adb devices | grep -q "emulator-"; then
    echo "❌ No Android emulator detected. Please start an emulator first."
    echo "💡 You can start an emulator from Android Studio or using:"
    echo "   flutter emulators --launch <emulator_name>"
    exit 1
fi

echo "📱 Emulator detected, proceeding with launch..."

# Navigate to the Flutter project directory
cd "$(dirname "$0")"

# Get dependencies
echo "📦 Getting Flutter dependencies..."
flutter pub get

# Launch the app
echo "🚀 Starting MITA app on emulator..."
flutter run --device-id emulator-5554