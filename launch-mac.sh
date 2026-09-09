#!/bin/bash
# Start MySuperWhisper via the launchd LaunchAgent (com.local.mysuperwhisper).
# Use this after quitting the app to launch it again without re-running the
# whole launchctl bootstrap dance.
set -e

launchctl kickstart "gui/$(id -u)/com.local.mysuperwhisper"
echo "MySuperWhisper started."
