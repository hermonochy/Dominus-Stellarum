#!/bin/bash

# build.sh - Cross-platform build script

echo "Building..."

# Windows build
wine pyinstaller.exe --onefile --windowed --name="Dominus Stellarum" main.py

# Linux build
pyinstaller --onefile --windowed --name="Dominus Stellarum" main.py
linuxdeploy --appdir AppDir --executable dist/DominusStellarum --output appimage

# macOS build (run on Mac)
#pyinstaller --onefile --windowed --icon=icon.icns --name="CosmicCollector-Mac" main.py

echo "Build complete!"
