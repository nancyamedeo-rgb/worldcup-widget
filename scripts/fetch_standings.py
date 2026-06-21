#!/usr/bin/env python3
"""
Fetches FIFA World Cup 2026 group standings from football-data.org
and writes them to data/standings.json for the Dakboard widget to consume
via raw.githubusercontent.com.

Requires the FOOTBALL_DATA_API_KEY environment variable (set as a
GitHub Actions secret — get a free key at https://www.football-data.org/client/register).
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

API_URL = "https://api.football-data.org/v4/competitions/WC/standings"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "standings.json")

# Maps football-data.org group labels (e.g. "GROUP A", "GROUP_A", or "A")
# to a single letter, e.g. "A".
def group_letter(raw_group):
    if not raw_group:
        return None
    cleaned = raw_group.strip().upper()
    cleaned = cleaned.replace("GROUP_", "").replace("GROUP ", "")
    return cleaned.strip()


def fetch_standings(api_key):
    req = urllib.request.Request(API_URL, headers={"X-Auth-Token": api_key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from football-data.org: {body[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error reaching football-data.org: {e}")


def transform(raw):
    """Convert football-data.org's standings payload into the flat
    {A: [...4 teams...], B: [...], ...} shape the widget expects."""
    groups = {}
    for block in raw.get("standings", []):
        letter = group_letter(block.get("group"))
        if not letter:
            continue
        table = []
        for row in block.get("table", []):
            team = row.get("team", {})
            table.append({
                "name": team.get("name", "Unknown"),
                "shortName": team.get("shortName") or team.get("name", "Unknown"),
                "tla": team.get("tla", ""),
                "crest": team.get("crest", ""),
                "gp": row.get("playedGames", 0),
                "w": row.get("won", 0),
                "d": row.get("draw", 0),
                "l": row.get("lost", 0),
                "gf": row.get("goalsFor", 0),
                "ga": row.get("goalsAgainst", 0),
                "gd": row.get("goalDifference", 0),
                "pts": row.get("points", 0),
            })
        groups[letter] = table
    return groups


def main():
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_key:
        print("ERROR: FOOTBALL_DATA_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Load previous data so we still have something valid to serve if the
    # fetch fails for any reason (rate limit, API hiccup, etc).
    previous = None
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r") as f:
                previous = json.load(f)
        except (json.JSONDecodeError, OSError):
            previous = None

    try:
        raw = fetch_standings(api_key)
        groups = transform(raw)
        if not groups:
            raise RuntimeError("No groups parsed from response — unexpected API shape.")

        output = {
            "groups": groups,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "football-data.org",
            "status": "ok",
        }
        print(f"Fetched standings for {len(groups)} groups.")

    except Exception as e:
        print(f"WARNING: fetch failed: {e}", file=sys.stderr)
        if previous:
            # Keep serving last-known-good data, just flag it as stale.
            output = previous
            output["status"] = "stale"
            output["lastError"] = str(e)
            output["lastErrorAt"] = datetime.now(timezone.utc).isoformat()
            print("Falling back to previous cached data.")
        else:
            # Nothing to fall back to — write an explicit error file so the
            # widget can show a clear message instead of silently breaking.
            output = {
                "groups": {},
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "source": "football-data.org",
                "status": "error",
                "lastError": str(e),
            }
            with open(OUTPUT_PATH, "w") as f:
                json.dump(output, f, indent=2)
            sys.exit(1)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
