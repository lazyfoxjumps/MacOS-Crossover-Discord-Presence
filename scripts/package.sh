#!/bin/sh
# Rolls dist/MacOS-Crossover-Discord-Presence-<version>.zip, the download people install from.
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-0.1-beta}"
NAME="MacOS-Crossover-Discord-Presence"
STAGE="$ROOT/dist/$NAME"

rm -rf "$STAGE" "$ROOT/dist/$NAME-$VERSION.zip"
mkdir -p "$STAGE"
cp "$ROOT/crossover_discord_presence.py" "$ROOT/games-seed.json.gz" \
   "$ROOT/install.sh" "$ROOT/uninstall.sh" "$ROOT/Install.command" "$ROOT/Uninstall.command" \
   "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$ROOT/LICENSE" "$STAGE/"
[ -f "$ROOT/config.json" ] && cp "$ROOT/config.json" "$STAGE/"
chmod +x "$STAGE/install.sh" "$STAGE/uninstall.sh" "$STAGE/Install.command" "$STAGE/Uninstall.command"

# ditto keeps the executable bits, so the .command files stay double-clickable after unzipping.
(cd "$ROOT/dist" && ditto -c -k --norsrc --noextattr --keepParent "$NAME" "$NAME-$VERSION.zip")
rm -rf "$STAGE"
echo "Packaged dist/$NAME-$VERSION.zip"
