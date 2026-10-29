#!/usr/bin/env python3
"""MacOS Crossover Discord Presence

Show Discord "Playing ..." status for Windows games running under Wine on macOS.

Discord for Mac only detects Mac apps, so games running in CrossOver, Whisky or
plain Wine never show up. This watches for Windows .exe processes, identifies the
game, and sets presence over Discord's local IPC socket with the game's real
Discord application ID, so the name and icon are the official ones.

A running game is identified by, in order:
  1. its .exe, against Discord's detectable-games list (what Discord does on Windows)
  2. its Steam app ID or Epic catalog ID, read from the launcher's install manifests
  3. its official store name or install folder name, against Discord's game names
  4. a fallback Discord app (optional, see FALLBACK_APP_ID) for games Discord doesn't know

Discord's list refreshes daily, so new games work without reinstalling. Uses only
the Python standard library.
"""

import glob
import gzip
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import uuid

DETECTABLE_URL = "https://discord.com/api/v9/applications/detectable"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_FILE = os.path.join(APP_DIR, "games-seed.json.gz")  # offline copy shipped with the installer
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
CACHE_DIR = os.path.expanduser("~/Library/Caches/crossover-discord-presence")
CACHE_FILE = os.path.join(CACHE_DIR, "games-v3.json")
CACHE_MAX_AGE = 24 * 60 * 60
POLL_SECONDS = 10
MANIFEST_RESCAN_SECONDS = 60

# Discord app used for games Discord has never heard of. Its name shows as "Playing <app name>"
# with the real game name underneath. Empty disables it; config.json can set "fallback_app_id".
FALLBACK_APP_ID = ""

# Wine processes show up in `ps` with their Windows path, e.g. "C:\Program Files\Game\game.exe -arg".
WINE_EXE = re.compile(r"^([a-z]:\\.*?\.exe)\b(.*)$", re.IGNORECASE)

# Store install folders. Only exes inside one of these count as games for name/fallback matching.
GAME_FOLDER = re.compile(
    r"/(?:steamapps/common|epic games|gog games|gog galaxy/games|ea games|ubisoft game launcher/games"
    r"|amazon games/library|xboxgames)/([^/]+)/")

# Never treat these as games: Wine itself and the store clients and their helpers.
IGNORED_DIRS = ("c:/windows/",)
IGNORED_EXES = {
    "steam.exe", "steamwebhelper.exe", "steamservice.exe", "steamerrorreporter.exe",
    "gameoverlayui.exe", "gameoverlayui64.exe",
    "epicgameslauncher.exe", "epicwebhelper.exe", "crashpad_handler.exe",
    "unitycrashhandler64.exe", "unitycrashhandler32.exe", "crashreportclient.exe",
}
# Installers and redistributables that live inside game folders.
IGNORED_EXE_WORDS = re.compile(r"redist|setup|install|uninst|vcredist|dxsetup|crash|easyanticheat_setup")
IGNORED_FOLDERS = {"steamworks shared", "steam controller configs"}

# Where Wine prefixes live for the common Mac Wine apps.
BOTTLE_GLOBS = [
    "~/Library/Application Support/CrossOver/Bottles/*",
    "~/Library/Containers/com.isaacmarovitz.Whisky/Bottles/*",
    "~/Applications/Sikarugir/*.app/Contents/SharedSupport/prefix",
    "/Applications/Sikarugir/*.app/Contents/SharedSupport/prefix",
    "~/Applications/Wineskin/*.app/Contents/SharedSupport/prefix",
    "/Applications/Wineskin/*.app/Contents/SharedSupport/prefix",
    "~/Applications/Kegworks/*.app/Contents/SharedSupport/prefix",
    "~/.wine",
]

OP_HANDSHAKE, OP_FRAME, OP_CLOSE = 0, 1, 2


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


# ---------- Discord's game list ----------

def build_games(apps):
    exes, names, skus = [], [], {}
    for app in apps:
        ref = [app["id"], app["name"]]
        for name in [app["name"]] + (app.get("aliases") or []):
            if normalize_name(name):
                names.append([normalize_name(name)] + ref)
        for sku in app.get("third_party_skus") or []:
            if sku.get("distributor") in ("steam", "epic", "gog") and sku.get("id"):
                skus.setdefault(f"{sku['distributor']}:{sku['id'].lower()}", ref)
        for exe in app.get("executables") or []:
            if exe.get("os") != "win32" or exe.get("is_launcher"):
                continue
            name = (exe.get("name") or "").lower().replace("\\", "/")
            if name:
                exes.append([name, exe.get("arguments") or ""] + ref)
    return {"exes": exes, "names": names, "skus": skus}


def download_games():
    req = urllib.request.Request(DETECTABLE_URL, headers={"User-Agent": "crossover-discord-presence"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        games = build_games(json.load(resp))
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(games, f)
    os.replace(tmp, CACHE_FILE)
    return games


def load_games():
    """Fresh cache, else download, else stale cache, else the offline seed shipped with the install."""
    fresh = os.path.exists(CACHE_FILE) and time.time() - os.path.getmtime(CACHE_FILE) < CACHE_MAX_AGE
    if not fresh:
        try:
            games = download_games()
            log(f"downloaded Discord game list ({len(games['skus'])} store IDs, {len(games['exes'])} exes)")
            return games
        except Exception as e:
            log(f"couldn't download game list: {e}")
    for path, opener in ((CACHE_FILE, open), (SEED_FILE, gzip.open)):
        try:
            with opener(path, "rt") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return {}


# ---------- local store manifests ----------

def bottles():
    for pattern in BOTTLE_GLOBS:
        for bottle in glob.glob(os.path.expanduser(pattern)):
            if os.path.isdir(os.path.join(bottle, "drive_c")):
                yield bottle


def windows_to_mac(bottle, win_path):
    """Map a path like D:\\SteamLibrary inside a bottle to its Mac location via dosdevices."""
    m = re.match(r"^([a-zA-Z]):[\\/]*(.*)$", win_path)
    if not m:
        return None
    root = os.path.join(bottle, "dosdevices", m.group(1).lower() + ":")
    if not os.path.exists(root):
        root = os.path.join(bottle, "drive_c") if m.group(1).lower() == "c" else None
    return root and os.path.join(root, m.group(2).replace("\\", "/"))


def scan_manifests():
    """Return {install folder (normalized): [(store key, official name), ...]} across all bottles."""
    found = {}

    def add(folder, key, name):
        entries = found.setdefault(normalize_name(os.path.basename(folder.rstrip("/\\"))), []) if folder else None
        if entries is not None and (key, name) not in entries:
            entries.append((key, name))

    for bottle in bottles():
        c = os.path.join(bottle, "drive_c")
        steamapps = {os.path.join(c, d, "Steam", "steamapps") for d in ("Program Files (x86)", "Program Files")}
        for lib in list(steamapps):
            try:
                with open(os.path.join(lib, "libraryfolders.vdf"), errors="ignore") as f:
                    for p in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                        mac = windows_to_mac(bottle, p.replace("\\\\", "\\"))
                        if mac:
                            steamapps.add(os.path.join(mac, "steamapps"))
            except OSError:
                pass
        for lib in steamapps:
            for acf in glob.glob(os.path.join(lib, "appmanifest_*.acf")):
                try:
                    with open(acf, errors="ignore") as f:
                        text = f.read()
                except OSError:
                    continue
                fields = dict(re.findall(r'"(appid|name|installdir)"\s+"([^"]*)"', text))
                if fields.get("appid") and fields.get("installdir"):
                    add(fields["installdir"], f"steam:{fields['appid']}", fields.get("name", ""))

        epic = os.path.join(c, "ProgramData", "Epic", "EpicGamesLauncher", "Data", "Manifests", "*.item")
        for item in glob.glob(epic):
            try:
                with open(item, errors="ignore") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            folder = (data.get("InstallLocation") or "").replace("\\", "/")
            for key in ("CatalogItemId", "CatalogNamespace", "AppName"):
                if data.get(key):
                    add(folder, f"epic:{data[key].lower()}", data.get("DisplayName", ""))

        for info in glob.glob(os.path.join(c, "*", "*", "goggame-*.info")) + \
                glob.glob(os.path.join(c, "*", "*", "*", "goggame-*.info")):
            try:
                with open(info, errors="ignore") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            add(os.path.dirname(info), f"gog:{str(data.get('gameId', '')).lower()}", data.get("name", ""))
    return found


# ---------- matching ----------

class Matcher:
    def __init__(self, games, fallback_app_id):
        # Index by file name so each running process only checks a handful of entries.
        self.by_basename = {}
        for name, args, app_id, label in games.get("exes", []):
            exact = name.startswith(">")
            name = name.lstrip(">")
            base = name.rsplit("/", 1)[-1]
            self.by_basename.setdefault(base, []).append((name, exact, args.lower(), app_id, label))
        self.by_name = {}
        for norm, app_id, label in games.get("names", []):
            self.by_name.setdefault(norm, (app_id, label))
        self.skus = games.get("skus", {})
        self.fallback_app_id = fallback_app_id
        self.manifests = {}
        self.scanned_at = 0

    def _manifest_entries(self, folder_norm):
        # Rescan when we meet a folder we don't know yet (a game installed since the last scan).
        if folder_norm not in self.manifests and time.time() - self.scanned_at > MANIFEST_RESCAN_SECONDS:
            self.manifests = scan_manifests()
            self.scanned_at = time.time()
        return self.manifests.get(folder_norm, [])

    def match(self, path, args):
        """path: lowercase Windows path with forward slashes. Returns (app_id, label, details) or None."""
        base = path.rsplit("/", 1)[-1]

        # 1. Discord's exe list.
        for name, exact, need_args, app_id, label in self.by_basename.get(base, ()):
            ok = name == base if exact else (path == name or path.endswith("/" + name))
            if ok and need_args in args:
                return app_id, label, None

        folder = GAME_FOLDER.search(path)
        if not folder or folder.group(1) in IGNORED_FOLDERS or IGNORED_EXE_WORDS.search(base):
            return None
        folder_norm = normalize_name(folder.group(1))
        entries = self._manifest_entries(folder_norm)

        # 2. Store IDs from the launcher's manifests.
        for key, _ in entries:
            if key in self.skus:
                app_id, label = self.skus[key]
                return app_id, label, None

        # 3. Official store name, then the folder name itself.
        official = next((name for _, name in entries if name), "")
        for candidate in (official, folder.group(1)):
            hit = self.by_name.get(normalize_name(candidate)) if candidate else None
            if hit:
                return hit[0], hit[1], None

        # 4. Unknown to Discord: show it under the fallback app with its real name.
        if self.fallback_app_id:
            label = official or folder.group(1).title()
            return self.fallback_app_id, label, label
        return None


def running_games(matcher):
    """Return {app_id: (label, details)} for every game running under Wine."""
    out = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True).stdout
    found = {}
    for line in out.splitlines():
        m = WINE_EXE.match(line.strip())
        if not m:
            continue
        path = m.group(1).lower().replace("\\", "/")
        if path.startswith(IGNORED_DIRS) or path.rsplit("/", 1)[-1] in IGNORED_EXES:
            continue
        hit = matcher.match(path, m.group(2).lower())
        if hit:
            found.setdefault(hit[0], (hit[1], hit[2]))
    return found


def load_fallback_app_id():
    try:
        with open(CONFIG_FILE) as f:
            return str(json.load(f).get("fallback_app_id") or FALLBACK_APP_ID)
    except (OSError, ValueError):
        return FALLBACK_APP_ID


# ---------- Discord IPC ----------

def temp_dir():
    # Discord's socket lives in the per-user temp dir; launchd agents don't always get $TMPDIR.
    if os.environ.get("TMPDIR"):
        return os.environ["TMPDIR"]
    out = subprocess.run(["getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True, text=True)
    return out.stdout.strip() or "/tmp/"


class DiscordIPC:
    def __init__(self, client_id):
        self.client_id = client_id
        self.sock = None

    def connect(self):
        base = temp_dir()
        for i in range(10):
            path = os.path.join(base, f"discord-ipc-{i}")
            if not os.path.exists(path):
                continue
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(5)
            try:
                s.connect(path)
                self.sock = s
                self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
                _, data = self._recv()
                if data.get("evt") == "READY":
                    return True
                log(f"handshake rejected on {path}: {data}")
            except (OSError, ValueError):
                pass
            s.close()
            self.sock = None
        return False

    def _send(self, op, payload):
        body = json.dumps(payload).encode()
        self.sock.sendall(struct.pack("<II", op, len(body)) + body)

    def _recv(self):
        op, length = struct.unpack("<II", self._recv_exact(8))
        return op, json.loads(self._recv_exact(length))

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Discord closed the socket")
            buf += chunk
        return buf

    def set_activity(self, start, details=None):
        activity = {"timestamps": {"start": start * 1000}}
        if details:
            activity["details"] = details
        self._send(OP_FRAME, {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity},
            "nonce": str(uuid.uuid4()),
        })
        _, data = self._recv()
        if data.get("evt") == "ERROR":
            raise ConnectionError(f"SET_ACTIVITY failed: {data.get('data')}")

    def alive(self):
        try:
            self.sock.setblocking(False)
            return self.sock.recv(1, socket.MSG_PEEK) != b""
        except BlockingIOError:
            return True
        except OSError:
            return False
        finally:
            if self.sock:
                self.sock.settimeout(5)

    def close(self):
        if self.sock:
            try:
                self._send(OP_CLOSE, {})
            except OSError:
                pass
            self.sock.close()
            self.sock = None


# ---------- main loop ----------

def main():
    games = load_games()
    if not games:
        log("no game list available yet, will retry")
    matcher = Matcher(games, load_fallback_app_id())
    loaded_at = time.time()
    active = {}  # app_id -> (DiscordIPC, label)
    log("watching for Windows games under Wine")

    while True:
        if time.time() - loaded_at > CACHE_MAX_AGE or not games:
            games = load_games()
            matcher = Matcher(games, load_fallback_app_id())
            loaded_at = time.time()

        running = running_games(matcher)

        for app_id in list(active):
            ipc, label = active[app_id]
            if app_id not in running:
                log(f"stopped: {label}")
            elif not ipc.alive():
                log(f"lost Discord connection for {label}, reconnecting")
            else:
                continue
            ipc.close()
            del active[app_id]

        for app_id, (label, details) in running.items():
            if app_id in active:
                continue
            ipc = DiscordIPC(app_id)
            try:
                if ipc.connect():
                    ipc.set_activity(int(time.time()), details)
                    active[app_id] = (ipc, label)
                    log(f"playing: {label}")
                else:
                    ipc.close()
            except (OSError, ConnectionError, ValueError) as e:
                log(f"{label}: {e}")
                ipc.close()

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
