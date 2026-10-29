#!/usr/bin/env python3
"""Refresh games-seed.json.gz, the offline copy of Discord's game list shipped in releases."""

import gzip
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import crossover_discord_presence as cdp  # noqa: E402

req = urllib.request.Request(cdp.DETECTABLE_URL, headers={"User-Agent": "crossover-discord-presence"})
with urllib.request.urlopen(req, timeout=60) as resp:
    games = cdp.build_games(json.load(resp))

out = os.path.join(ROOT, "games-seed.json.gz")
with gzip.open(out, "wt", compresslevel=9) as f:
    json.dump(games, f, separators=(",", ":"))
print(f"wrote {out}: {len(games['skus'])} store IDs, {len(games['names'])} names, {len(games['exes'])} exes")
