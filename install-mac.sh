#!/bin/bash
# Installs MySuperWhisper as a standalone macOS app:
#   1. Provisions a standalone Python 3.13 via `uv` (independent of Homebrew,
#      so unrelated `brew upgrade` runs can never invalidate the Accessibility
#      permission this app depends on).
#   2. Creates/refreshes the project venv and installs dependencies.
#   3. Freezes the app with PyInstaller into MySuperWhisper.app and installs
#      it to /Applications.
#   4. Registers a per-user LaunchAgent so it starts automatically at login.
#
# Safe to re-run: rebuilds the app in place and restarts the LaunchAgent.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="MySuperWhisper.app"
INSTALLED_APP="/Applications/$APP_NAME"
LAUNCH_AGENT_LABEL="com.local.mysuperwhisper"
LAUNCH_AGENT_PLIST="$HOME/Library/LaunchAgents/$LAUNCH_AGENT_LABEL.plist"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

step() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}!!${NC} $1"; }

if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script is for macOS only. Use install.sh on Linux." >&2
    exit 1
fi

step "Checking for uv..."
if ! command -v uv &>/dev/null; then
    if command -v brew &>/dev/null; then
        brew install uv
    else
        echo "uv is required. Install it from https://docs.astral.sh/uv/ and re-run this script." >&2
        exit 1
    fi
fi

step "Provisioning a standalone Python 3.13 (managed by uv, not Homebrew)..."
uv python install 3.13

step "Creating project virtual environment..."
rm -rf "$PROJECT_DIR/.venv"
uv venv --python 3.13 "$PROJECT_DIR/.venv"

step "Installing dependencies..."
uv pip install --python "$PROJECT_DIR/.venv/bin/python" -e "$PROJECT_DIR[macos-build]"

step "Building MySuperWhisper.app..."
rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist"
(cd "$PROJECT_DIR" && "$PROJECT_DIR/.venv/bin/pyinstaller" packaging/mysuperwhisper.spec --noconfirm)

step "Installing app to /Applications..."
if launchctl list "$LAUNCH_AGENT_LABEL" &>/dev/null; then
    launchctl bootout "gui/$(id -u)/$LAUNCH_AGENT_LABEL" 2>/dev/null || true
fi
rm -rf "$INSTALLED_APP"
cp -R "$PROJECT_DIR/dist/$APP_NAME" "$INSTALLED_APP"
codesign --force --deep --sign - "$INSTALLED_APP"
rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist"

step "Registering LaunchAgent..."
mkdir -p "$HOME/Library/LaunchAgents"
sed \
    -e "s#__APP_EXECUTABLE__#$INSTALLED_APP/Contents/MacOS/MySuperWhisper#g" \
    -e "s#__HOME__#$HOME#g" \
    "$PROJECT_DIR/packaging/com.local.mysuperwhisper.plist.template" > "$LAUNCH_AGENT_PLIST"

rm -f /tmp/mysuperwhisper.lock /tmp/mysuperwhisper.sock
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENT_PLIST"

echo ""
echo -e "${GREEN}Installed.${NC} MySuperWhisper is running from $INSTALLED_APP"
echo ""
warn "One manual step remains: grant Accessibility permission."
echo "   System Settings > Privacy & Security > Accessibility > add $INSTALLED_APP and enable it."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true
