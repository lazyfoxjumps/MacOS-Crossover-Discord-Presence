#!/bin/sh
# Installs MacOS Crossover Discord Presence for the current user and starts it at every login.
# Safe to run again: it updates an existing install in place.
set -e

NAME="crossover-discord-presence"
LABEL="com.lazyfoxjumps.$NAME"
APP_DIR="$HOME/Library/Application Support/$NAME"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/$NAME.log"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

# macOS ships /usr/bin/python3 as a stub until the Command Line Tools are installed.
PYTHON=""
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "$p" ] && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>/dev/null; then
        PYTHON="$p"; break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "Python 3.8+ not found. Run: xcode-select --install   then run this installer again." >&2
    exit 1
fi

# Clean up the pre-release build, which ran under the name wine-presence.
launchctl bootout "gui/$(id -u)/com.wine-presence.agent" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.wine-presence.agent.plist"
rm -rf "$HOME/Library/Application Support/wine-presence" "$HOME/Library/Caches/wine-presence"
rm -f "$HOME/Library/Logs/wine-presence.log"

mkdir -p "$APP_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cp "$SRC_DIR/crossover_discord_presence.py" "$APP_DIR/crossover_discord_presence.py"
# Offline copy of Discord's game list, used until the first daily download succeeds.
cp "$SRC_DIR/games-seed.json.gz" "$APP_DIR/games-seed.json.gz" 2>/dev/null || true
# Keep an existing config.json (fallback app ID) across reinstalls.
[ -f "$APP_DIR/config.json" ] || [ ! -f "$SRC_DIR/config.json" ] || cp "$SRC_DIR/config.json" "$APP_DIR/config.json"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>-I</string>
        <string>$APP_DIR/crossover_discord_presence.py</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>ProcessType</key><string>Background</string>
    <key>StandardOutPath</key><string>$LOG</string>
    <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "MacOS Crossover Discord Presence is installed and running (Python: $PYTHON)."
echo "Log: $LOG"
