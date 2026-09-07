#!/usr/bin/env python3
"""Fetch, normalize, and archive NFL game lines and player props."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

API_ROOT = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
PROP_COLUMNS = [
    "Season", "Week", "Event ID", "Commence Time", "Bookmaker", "Book Key",
    "Last Update", "Home", "Away", "Player", "Team", "Opponent", "Position",
    "Market Key", "Market Window", "Line", "Side", "American Odds", "Pair Key",
    "Raw Implied", "No-Vig Implied", "Source URL"
]
GAME_COLUMNS = [
    "Season", "Week", "Event ID", "Commence Time", "Bookmaker", "Last Update",
    "Away", "Home", "Market", "Team / Side", "Line", "American Odds",
    "Raw Implied", "Pair Key", "No-Vig Implied", "Source URL"
]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def american_implied(price: float | int | None) -> float | None:
    if price is None or price == 0:
        return None
    price = float(price)
    return (-price / (-price + 100.0)) if price < 0 else (100.0 / (price + 100.0))


def infer_week(when: dt.datetime, season_start: dt.datetime) -> int:
    return max(1, min(18, ((when.date() - season_start.date()).days // 7) + 1))


def api_get(path: str, api_key: str, params: dict | None = None) -> tuple[object, dict]:
    query = dict(params or {})
    query["apiKey"] = api_key
    url = API_ROOT + path + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": "nfl-player-prop-opportunity/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
            quota = {
                "requests_remaining": response.headers.get("x-requests-remaining"),
                "requests_used": response.headers.get("x-requests-used"),
                "requests_last": response.headers.get("x-requests-last"),
            }
            return data, quota
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Odds API HTTP %s: %s" % (exc.code, body[:500])) from exc


def paired_no_vig(rows: list[dict], pair_field: str = "Pair Key") -> None:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        raw = row.get("Raw Implied")
        if raw not in (None, ""):
            totals[str(row[pair_field])] += float(raw)
    for row in rows:
        raw = row.get("Raw Implied")
        total = totals.get(str(row.get(pair_field)), 0.0)
        row["No-Vig Implied"] = round(float(raw) / total, 8) if raw not in (None, "") and total > 0 else ""


def normalize_props(events: list[dict], season: int, week: int, source_url: str) -> list[dict]:
    rows: list[dict] = []
    for event in events:
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                key = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    player = outcome.get("description", "")
                    side = outcome.get("name", "")
                    line = outcome.get("point", "")
                    price = outcome.get("price")
                    pair = "%s|%s|%s|%s" % (book.get("key", ""), player, key, line)
                    position = "RB" if key.startswith("player_rush") else "WR" if key.startswith("player_reception") else ""
                    rows.append({
                        "Season": season, "Week": week, "Event ID": event.get("id", ""),
                        "Commence Time": event.get("commence_time", ""), "Bookmaker": book.get("title", ""),
                        "Book Key": book.get("key", ""), "Last Update": market.get("last_update", book.get("last_update", "")),
                        "Home": event.get("home_team", ""), "Away": event.get("away_team", ""),
                        "Player": player, "Team": "", "Opponent": "", "Position": position,
                        "Market Key": key, "Market Window": "Full Game", "Line": line, "Side": side,
                        "American Odds": price if price is not None else "", "Pair Key": pair,
                        "Raw Implied": round(american_implied(price), 8) if american_implied(price) is not None else "",
                        "No-Vig Implied": "", "Source URL": source_url,
                    })
    paired_no_vig(rows)
    return rows


def normalize_game_lines(events: list[dict], season: int, week: int, source_url: str) -> list[dict]:
    rows: list[dict] = []
    for event in events:
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                key = market.get("key", "")
                outcomes = market.get("outcomes", [])
                for outcome in outcomes:
                    line = outcome.get("point", "")
                    price = outcome.get("price")
                    pair_line = line if key == "totals" else "event"
                    pair = "%s|%s|%s|%s" % (book.get("key", ""), event.get("id", ""), key, pair_line)
                    rows.append({
                        "Season": season, "Week": week, "Event ID": event.get("id", ""),
                        "Commence Time": event.get("commence_time", ""), "Bookmaker": book.get("title", ""),
                        "Last Update": market.get("last_update", book.get("last_update", "")),
                        "Away": event.get("away_team", ""), "Home": event.get("home_team", ""),
                        "Market": key, "Team / Side": outcome.get("name", ""), "Line": line,
                        "American Odds": price if price is not None else "",
                        "Raw Implied": round(american_implied(price), 8) if american_implied(price) is not None else "",
                        "Pair Key": pair, "No-Vig Implied": "", "Source URL": source_url,
                    })
    paired_no_vig(rows)
    return rows


def write_csv(path: pathlib.Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def post_webhook(url: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as response:
        if response.status >= 300:
            raise RuntimeError("Sheet webhook returned HTTP %s" % response.status)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--lookahead-hours", type=int, default=72)
    parser.add_argument("--regions", default="us", help="Regions used for game lines")
    parser.add_argument("--prop-regions", default="us,us_dfs", help="Regions used for player props; us_dfs includes Underdog")
    parser.add_argument("--markets", default="player_rush_yds,player_reception_yds")
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()

    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if not api_key:
        print("ODDS_API_KEY is required", file=sys.stderr)
        return 2

    now = utc_now()
    season_start = parse_iso(os.environ.get("NFL_SEASON_START", "2026-09-10T00:00:00Z"))
    week = int(os.environ.get("NFL_WEEK") or infer_week(now, season_start))
    cutoff = now + dt.timedelta(hours=args.lookahead_hours)
    source = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"

    events, quota = api_get("/sports/%s/events" % SPORT, api_key, {"dateFormat": "iso"})
    eligible = [e for e in events if now <= parse_iso(e["commence_time"]) <= cutoff]

    game_events, game_quota = api_get("/sports/%s/odds" % SPORT, api_key, {
        "regions": args.regions, "markets": "h2h,spreads,totals", "oddsFormat": "american", "dateFormat": "iso"
    })
    prop_payloads = []
    last_quota = quota
    for event in eligible:
        payload, last_quota = api_get("/sports/%s/events/%s/odds" % (SPORT, event["id"]), api_key, {
            "regions": args.prop_regions, "markets": args.markets, "oddsFormat": "american", "dateFormat": "iso"
        })
        prop_payloads.append(payload)

    props = normalize_props(prop_payloads, args.season, week, source)
    lines = normalize_game_lines(game_events, args.season, week, source)
    out = pathlib.Path(args.output_dir)
    latest = out / "latest"
    snapshot = out / "snapshots" / ("%s-W%02d" % (args.season, week))
    stamp = now.strftime("%Y%m%dT%H%M%SZ")

    write_csv(latest / "player_props.csv", PROP_COLUMNS, props)
    write_csv(latest / "game_lines.csv", GAME_COLUMNS, lines)
    write_json(latest / "events.json", eligible)
    status = {
        "generated_at": now.isoformat(), "season": args.season, "week": week,
        "lookahead_hours": args.lookahead_hours, "game_regions": args.regions.split(","),
        "prop_regions": args.prop_regions.split(","), "markets": args.markets.split(","),
        "eligible_events": len(eligible), "player_prop_rows": len(props), "game_line_rows": len(lines),
        "quota": last_quota or game_quota, "sheet_webhook_configured": bool(os.environ.get("SHEETS_WEBHOOK_URL")),
    }
    write_json(latest / "status.json", status)
    write_csv(snapshot / (stamp + "_player_props.csv"), PROP_COLUMNS, props)
    write_csv(snapshot / (stamp + "_game_lines.csv"), GAME_COLUMNS, lines)
    write_json(snapshot / (stamp + "_status.json"), status)

    webhook = os.environ.get("SHEETS_WEBHOOK_URL", "").strip()
    if webhook:
        post_webhook(webhook, {"status": status, "player_props": props, "game_lines": lines})

    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

