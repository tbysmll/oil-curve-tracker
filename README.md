# Oil Curve Tracker

A Python tool that tracks the shape of the Brent and WTI crude oil futures curves, flags when each moves
between backwardation and contango, and follows the Brent-WTI spread.

**Data sources**
- [EIA Open Data API](https://www.eia.gov/opendata/): Brent and WTI spot prices, plus WTI futures history (to April 2024)
- Yahoo Finance (via `yfinance`): live Brent (NYMEX BZ) and WTI (NYMEX CL) futures contracts, M1 to M12

**Status:** working end to end. A GitHub Actions workflow runs the tracker every weekday at 22:30 UK time
and commits the day's curves, charts and the table below.

**Web report:** https://tbysmll.github.io/oil-curve-tracker/ (today's numbers, charts and my commentary on one page)

## Latest numbers (updated automatically)

<!-- LATEST-NUMBERS:START -->

Run at 03 Nov 2026 11:02 UK time. Prices in $/bbl. Every row shows the date its prices come from.

### Today's numbers

| Measure | Value | Reading | Data date | Working |
|---|---:|---|---|---|
| Brent M1-M2 | +3.07 | backwardation | 02 Nov 2026 | 2027-01 minus 2027-02 |
| Brent M1-M6 | +11.71 | backwardation | 02 Nov 2026 | 2027-01 minus 2027-06 |
| Brent M1-M12 | +19.79 | backwardation | 02 Nov 2026 | 2027-01 minus 2027-12 |
| WTI M1-M2 | +1.52 | backwardation | 03 Nov 2026 | 2026-12 minus 2027-01 |
| WTI M1-M6 | +8.88 | backwardation | 03 Nov 2026 | 2026-12 minus 2027-05 |
| WTI M1-M12 | +16.94 | backwardation | 03 Nov 2026 | 2026-12 minus 2027-11 |
| Brent-WTI spot spread (EIA) | +19.73 | location spread | 27 Oct 2026 | Brent 123.10 minus WTI 103.37 |
| Dated Brent minus front-month future | +9.22 | spot above future | 27 Oct 2026 (latest date both sources have) | EIA 123.10 minus Yahoo BZ=F 113.88 |
| WTI M1-M2 percentile vs EIA history | 96.6 | percentile (not $/bbl) | today 03 Nov 2026; history 04 Jan 2010 to 05 Apr 2024 | 3,476 of 3,598 days at or below +1.52 |

### Charts

![curves](docs/charts/curves.png)

![brent_wti_spread](docs/charts/brent_wti_spread.png)

![m1_m6_fixed](docs/charts/m1_m6_fixed.png)

![wti_m1m2_history](docs/charts/wti_m1m2_history.png)

### Notes

- Brent and WTI curves can come from different days: each uses its latest day with all 12 contracts priced.
- If the tracker ran during US trading hours, the latest futures prices are live rather than closing prices.
- EIA spot prices run a few days behind; the WTI percentile deliberately compares today with 2010-2024.

<!-- LATEST-NUMBERS:END -->

## Setup
1. Install Python 3.10+.
2. In this folder: `python -m venv .venv`, then activate it
   (Windows: `.venv\Scripts\activate`, Mac: `source .venv/bin/activate`).
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and add your free EIA API key.

## Files
| File | What it does |
|---|---|
| `config.py` | All settings in one place |
| `eia.py` | Downloads EIA spot prices and WTI futures history |
| `futures.py` | Builds today's Brent and WTI curves; saves a daily snapshot to `data/` |
| `spreads.py` | Calculates time spreads, the Brent-WTI spread, Dated Brent vs futures and the WTI M1-M2 percentile |
| `charts.py` | Draws the four charts into `docs/charts/` |
| `report.py` | Builds the numbers table, the Markdown summary and the web report `docs/index.html` |
| `main.py` | Runs everything: snapshot, charts, `output/summary.md`, the web report and this README's latest numbers |
| `commentary.txt` | My own commentary, shown on the web report |
| `.github/workflows/daily-update.yml` | Runs `main.py` every weekday at 22:30 UK time and commits the results |
| `CLAUDE.md` | Instructions Claude Code follows when working on this project |
| `LEARNING_GUIDE.md` | Step-by-step guide to building the rest with Claude Code |
