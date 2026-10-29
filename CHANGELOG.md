# Changelog

All notable changes to MacOS Crossover Discord Presence are listed here.
This project follows [Keep a Changelog](https://keepachangelog.com/), and versions aim for
[Semantic Versioning](https://semver.org/).

## [0.1 beta] - 2026-10-29

The first public beta. 🎉 Windows games you play through CrossOver now show up on your Discord
profile, just like they do on Windows.

### Added

**Discord status for Wine games**
- Detects Windows games running under Wine and sets your Discord status to "Playing [game]", with
  the game's official name, icon and elapsed timer.
- Clears your status about 10 seconds after you quit the game.
- Reconnects on its own if Discord is restarted while you play.

**Game recognition**
- Matches the game's .exe against Discord's list of detectable games.
- Matches the game's Steam, Epic or GOG store ID, read from the install files inside your bottle.
  This catches the many games whose .exe Discord doesn't list.
- Matches the game's store name or install folder name against every game name Discord knows.
- Optional fallback app for games Discord doesn't know, set in `config.json`.
- Ignores things that aren't games: Wine's own processes, the Steam and Epic clients, overlays,
  crash reporters, installers and redistributables.

**Compatibility**
- Supports CrossOver, Whisky, Sikarugir, Wineskin, Kegworks and plain Wine, including extra Steam
  library drives.
- Downloads Discord's game list once a day, so new games work without reinstalling.
- Includes an offline copy of the game list for the first launch.

**Install and uninstall**
- Double-click `Install.command` (or run `sh install.sh`). It starts right away, at every login,
  and macOS restarts it if it ever crashes.
- The installer finds a suitable Python on its own and explains how to get one if it's missing.
- Running the installer again updates in place and keeps your `config.json`.
- Double-click `Uninstall.command` to remove everything.

### Known issues

- On your own screen, Discord redraws the timer less often while it's in the background. Friends
  see it ticking normally.
- Games that already set their own Discord status through a Wine bridge may show up twice.
