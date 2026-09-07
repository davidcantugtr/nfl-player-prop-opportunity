# NFL 2026 Vegas-Adjusted Player Opportunity

Automated sportsbook data layer for the RB Q1 and WR full-game opportunity models.

## Live model

- [Vegas-Adjusted RB & WR Opportunity Model](https://docs.google.com/spreadsheets/d/1qnzbmEaE_t12xHFV1Ip7rZT6OhAOSO_mQFjuPCuQrfQ/edit)
- RB evidence window: first quarter (Q1)
- WR evidence window: full game
- WR eligibility: season-to-date offensive snap share must be strictly greater than 20% once live snap data begins

## What the pipeline does

1. Retrieves upcoming NFL events and game lines from The Odds API.
2. Retrieves event-level player props for games inside the configured lookahead window.
3. Converts American odds to raw implied probability.
4. Removes bookmaker margin by normalizing paired outcomes.
5. Writes current CSV/JSON outputs plus timestamped weekly snapshots.
6. Optionally posts the normalized payload to a Google Apps Script webhook when `SHEETS_WEBHOOK_URL` is configured.

The default scheduled run uses only `player_rush_yds` and `player_reception_yds` to control API-credit usage. Manual expanded runs also include rushing attempts, receptions, and anytime touchdowns.

## Repository secret

The required repository secret is:

```text
ODDS_API_KEY
```

Never place the key in source code, CSV output, workflow logs, or the Google Sheet.

## Outputs

```text
data/latest/events.json
data/latest/player_props.csv
data/latest/game_lines.csv
data/latest/status.json
data/snapshots/YYYY-Www/
```

`player_props.csv` is ordered to match the Google Sheet's **Sportsbook Odds Input** tab. The workbook calculates its own consensus and blended tiers, while the normalized no-vig values remain available for audit.

## Manual run

Open **Actions → Refresh NFL sportsbook data → Run workflow**. Choose:

- `primary`: rushing yards and receiving yards
- `expanded`: adds rushing attempts, receptions, and anytime TD

The workflow never invents missing markets. A sportsbook or market that has not posted a price remains absent.

## Local execution

```bash
ODDS_API_KEY=your_key python scripts/refresh_odds.py --season 2026 --lookahead-hours 72
```

Run tests with:

```bash
python -m unittest discover -s tests -v
```

