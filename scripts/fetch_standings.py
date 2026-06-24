#!/usr/bin/env python3
"""
Fetches FIFA World Cup 2026 group standings AND today's scheduled matches
from football-data.org and writes them to data/standings.json for the
Dakboard widget to consume via raw.githubusercontent.com.

Requires FOOTBALL_DATA_API_KEY environment variable.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

STANDINGS_URL = "https://api.football-data.org/v4/competitions/WC/standings"
MATCHES_URL   = "https://api.football-data.org/v4/competitions/WC/matches"
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "standings.json")


def group_letter(raw_group):
    if not raw_group:
        return None
    cleaned = raw_group.strip().upper()
    cleaned = cleaned.replace("GROUP_", "").replace("GROUP ", "")
    return cleaned.strip()


def api_get(url, api_key):
    req = urllib.request.Request(url, headers={"X-Auth-Token": api_key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e}")


def transform_standings(raw):
    groups = {}
    for block in raw.get("standings", []):
        letter = group_letter(block.get("group"))
        if not letter:
            continue
        table = []
        for row in block.get("table", []):
            team = row.get("team", {})
            table.append({
                "name":      team.get("name", "Unknown"),
                "shortName": team.get("shortName") or team.get("name", "Unknown"),
                "tla":       team.get("tla", ""),
                "gp":  row.get("playedGames", 0),
                "w":   row.get("won", 0),
                "d":   row.get("draw", 0),
                "l":   row.get("lost", 0),
                "gf":  row.get("goalsFor", 0),
                "ga":  row.get("goalsAgainst", 0),
                "gd":  row.get("goalDifference", 0),
                "pts": row.get("points", 0),
            })
        groups[letter] = table
    return groups


def transform_matches(raw, today_str):
    """Return today's WC matches, sorted by kickoff time."""
    matches = []
    for m in raw.get("matches", []):
        utc_date = m.get("utcDate", "")
        # utcDate looks like "2026-06-23T18:00:00Z"
        if not utc_date.startswith(today_str):
            continue
        home = m.get("homeTeam", {})
        away = m.get("awayTeam", {})
        score = m.get("score", {})
        full  = score.get("fullTime", {})
        status = m.get("status", "SCHEDULED")  # SCHEDULED, TIMED, IN_PLAY, PAUSED, FINISHED

        # Parse kickoff time for display
        try:
            kickoff_utc = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            kickoff_et  = kickoff_utc - timedelta(hours=4)   # ET = UTC-4 (EDT)
            kickoff_str = kickoff_et.strftime("%-I:%M %p ET")
        except Exception:
            kickoff_str = utc_date[11:16] + " UTC"

        group_raw = m.get("group", "") or ""
        group = group_letter(group_raw) or "?"

        matches.append({
            "group":      group,
            "homeTeam":   home.get("shortName") or home.get("name") or "TBD",
            "awayTeam":   away.get("shortName") or away.get("name") or "TBD",
            "homeTLA":    home.get("tla", ""),
            "awayTLA":    away.get("tla", ""),
            "kickoff":    kickoff_str,
            "utcDate":    utc_date,
            "status":     status,
            "homeScore":  full.get("home"),
            "awayScore":  full.get("away"),
            "venue":      m.get("venue", ""),
        })

    matches.sort(key=lambda x: x["utcDate"])
    return matches


def main():
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_key:
        print("ERROR: FOOTBALL_DATA_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    previous = None
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r") as f:
                previous = json.load(f)
        except (json.JSONDecodeError, OSError):
            previous = None

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        raw_standings = api_get(STANDINGS_URL, api_key)
        groups = transform_standings(raw_standings)
        if not groups:
            raise RuntimeError("No groups parsed — unexpected API shape.")

        # Fetch today's matches (filter to WC group stage)
        url_with_date = f"{MATCHES_URL}?dateFrom={today_str}&dateTo={today_str}"
        try:
            raw_matches = api_get(url_with_date, api_key)
            today_matches = transform_matches(raw_matches, today_str)
            print(f"Fetched {len(today_matches)} matches for {today_str}.")
        except Exception as me:
            print(f"WARNING: match fetch failed: {me} — using empty list.", file=sys.stderr)
            today_matches = previous.get("todayMatches", []) if previous else []

        output = {
            "groups":       groups,
            "todayMatches": today_matches,
            "matchDate":    today_str,
            "updatedAt":    datetime.now(timezone.utc).isoformat(),
            "source":       "football-data.org",
            "status":       "ok",
        }
        print(f"Fetched standings for {len(groups)} groups.")

    except Exception as e:
        print(f"WARNING: fetch failed: {e}", file=sys.stderr)
        if previous:
            output = previous
            output["status"] = "stale"
            output["lastError"] = str(e)
            output["lastErrorAt"] = datetime.now(timezone.utc).isoformat()
            print("Falling back to previous cached data.")
        else:
            output = {
                "groups": {}, "todayMatches": [],
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "source": "football-data.org",
                "status": "error", "lastError": str(e),
            }
            with open(OUTPUT_PATH, "w") as f:
                json.dump(output, f, indent=2)
            sys.exit(1)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
