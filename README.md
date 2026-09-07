# NFL 2026 Vegas-Adjusted Player Opportunity

Automated sportsbook data layer for the RB Q1 and WR full-game opportunity models.

## Live model

- [Vegas-Adjusted RB & WR Opportunity Model](https://docs.google.com/spreadsheets/d/1qnzbmEaE_t12xHFV1Ip7rZT6OhAOSO_mQFjuPCuQrfQ/edit)
- RB evidence window: first quarter (Q1)
- WR evidence window: full game
- WR eligibility: season-to-date offensive snap share must be strictly greater than 20% once live snap data begins

## What the pipeline does

1. Retrieves upcoming NFL events and game lines from The Odds API.
2. Retrieves event-level sportsbook and DFS player props, including Underdog Fantasy (`us_dfs`), for games inside the configured lookahead window.
3. Converts American odds to raw implied probability.
4. Removes bookmaker margin by normalizing paired outcomes.
5. Writes current CSV/JSON outputs plus timestamped weekly snapshots.
6. Optionally posts the normalized payload to a Google Apps Script webhook when `SHEETS_WEBHOOK_URL` is configured.

The default scheduled run uses only `player_rush_yds` and `player_reception_yds` across the `us` and `us_dfs` prop regions to control API-credit usage. Manual expanded runs also include rushing attempts, receptions, and anytime touchdowns.

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

## Google Sheets auto-refresh

The live workbook contains **GitHub Prop Feed** and **GitHub Game Feed** tabs that use `IMPORTDATA` against this repository's current CSV outputs. Google requires a one-time external-data approval for each formula: open each feed tab in a desktop browser, select cell A1, and click **Allow access**. Until approval, the consensus engine safely falls back to the last verified values in the staging tabs.

This connection depends on the repository remaining public. If the repository becomes private, replace `IMPORTDATA` with the optional Apps Script webhook and add its deployment URL as the `SHEETS_WEBHOOK_URL` repository secret.

## Manual run

Open **Actions → Refresh NFL sportsbook data → Run workflow**. Choose:

- `primary`: rushing yards and receiving yards
- `expanded`: adds rushing attempts, receptions, and anytime TD

Underdog Fantasy is ingested as a dedicated pick’em source (`bookmaker key: underdog`) and should be evaluated separately from traditional sportsbook consensus because payout multipliers can vary with the selected combination. The workflow never invents missing markets. A sportsbook or market that has not posted a price remains absent.

## Local execution

```bash
ODDS_API_KEY=your_key python scripts/refresh_odds.py --season 2026 --lookahead-hours 72
```

Run tests with:

```bash
python -m unittest discover -s tests -v
```
