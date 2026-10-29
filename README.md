# MacOS Crossover Discord Presence 🎮

Show **"Playing [game]"** on your Discord profile for Windows games you play on a Mac through CrossOver.

## 🤔 What is this?

Discord on Mac only notices Mac apps. When you play a Windows game through CrossOver, Discord has no idea it's running, so your profile stays blank no matter how many hours you put in.

This is a small script that runs quietly in the background and fixes that. When you launch a game in CrossOver, it figures out which game it is and tells the Discord app on your Mac. Your profile then shows the game's official name, its icon, and the elapsed timer, the same as it would on Windows.

It also works with Whisky, Sikarugir, Wineskin, Kegworks and plain Wine.

## ✨ Features

- 🎯 **Automatic.** Launch a game, and within about 10 seconds your status updates. Quit, and it clears.
- 🏷️ **Official names and icons.** It uses each game's real Discord listing, not a generic "Wine" label.
- 🆕 **New games just work.** It downloads Discord's game list once a day, so nothing needs reinstalling when you add games.
- ✈️ **Works offline.** A copy of the game list is included, so it works on first launch even without internet.
- 🔒 **Doesn't touch your account.** No login, no token, no password. It only talks to the Discord app running on your Mac.
- 🪶 **Lightweight.** One Python file, no extra packages, and it starts by itself at login.

## ⬇️ Installation

1. Download **`MacOS-Crossover-Discord-Presence-0.1-beta.zip`** and unzip it.
2. Double-click **`Install.command`**.
3. Launch a game in CrossOver and check your Discord profile. 🎉

That's it. It's now running, and it starts automatically every time you log in.

Prefer Terminal? Run `sh install.sh` from the unzipped folder instead.

### Requirements

- **macOS** with **Python 3.8 or newer**. If the installer says Python is missing, run `xcode-select --install`, let it finish, then run the installer again.
- **The Discord desktop app**, open while you play.
- **Activity sharing turned on** in Discord: Settings → Activity Privacy → "Share your detected activities with others".

### 😬 "Install.command can't be opened"

macOS is cautious about scripts downloaded from the internet. Right-click **`Install.command`**, choose **Open**, then click **Open** again. You only need to do this once.

## 🕵️ How it recognizes your game

It checks these in order, and stops at the first match:

1. **The game's .exe file**, against Discord's own list of games (the same check Discord does on Windows).
2. **The game's store ID**, read from the Steam, Epic or GOG install files inside your CrossOver bottle. This one matters, because Discord doesn't list the .exe for over half of its games.
3. **The game's name**, from the store or the install folder, against every game name Discord knows.
4. **A fallback** for games Discord has never heard of (optional, see below).

Steps 1 to 3 cover nearly everything on Steam with zero setup.

## 🧩 Optional: show games Discord doesn't know

Discord needs an app listing to show any game. For the rare game that has none, you can create a stand-in:

1. Create a free application in the [Discord Developer Portal](https://discord.com/developers/applications). Name it what you'd like your status to say, for example **"a game on Mac"**.
2. Copy its **Application ID** into a file named `config.json`, in the same folder as `install.sh`:

   ```json
   { "fallback_app_id": "123456789012345678" }
   ```

3. Run the installer again.

Unknown games will then show as **Playing a game on Mac**, with the real game name underneath. The ID isn't secret, so it's fine to share with friends.

## 🛠️ Troubleshooting

**My game doesn't show up.**
1. Make sure the Discord app is open and activity sharing is on (see Requirements).
2. Check the log at `~/Library/Logs/crossover-discord-presence.log`. Every game it detects gets a `playing:` line.
3. Still nothing? Discord may not have that game listed at all. The fallback above will cover it.

**The timer on my own screen freezes and jumps.**
That's Discord, not this script. When Discord isn't the app in front, it saves battery by redrawing less often. Click into Discord and it catches up. Your friends see the timer ticking normally. ⏱️

**A game shows up twice.**
Some games set their own Discord status through a Wine bridge. If you use one of those, you might see both.

## 👋 Uninstall

Double-click **`Uninstall.command`**, or run `sh uninstall.sh`. It stops the script and removes all of its files, its cache and its log.

## 🧑‍💻 For developers

```bash
python3 crossover_discord_presence.py   # run in the foreground and watch the output
python3 scripts/update-seed.py          # refresh the bundled offline game list
sh scripts/package.sh                   # build dist/MacOS-Crossover-Discord-Presence-0.1-beta.zip
```

How it works: the script lists running processes and keeps the ones with Windows paths (that's how Wine programs appear on a Mac). It identifies each game, connects to the Discord app's local `discord-ipc` socket using that game's Discord app ID, and sets the activity. It runs as a regular user LaunchAgent, `~/Library/LaunchAgents/com.lazyfoxjumps.crossover-discord-presence.plist`.

## 📜 License

[MIT](LICENSE). Use it, share it, change it. Have fun. 💛
