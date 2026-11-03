"""
main.py - runs the whole tracker once: download, check, calculate, chart, write the summary, save today's curves.

Run it with:  python main.py
It writes:
  data/curve_snapshots.csv  - today's Brent and WTI curves added to the daily history
  output/summary.md         - a table of today's numbers, each with the date its prices come from, plus the charts
  output/*.png              - the four charts (see charts.py)
  README.md                 - the "Latest numbers" section is replaced with today's table and charts

Run it once a day, in the evening after US markets close, so the snapshot stores closing prices
rather than live ones. If it runs twice on the same day, the later run replaces that day's snapshot.
GitHub Actions runs it automatically every weekday at 22:30 UK time (.github/workflows/daily-update.yml).

If any download fails or the data looks wrong, the run stops with an error BEFORE anything is saved,
so a bad day never gets written into the history (or committed to GitHub).
"""

import datetime as dt                              # dt gives today's date and the current time
from config import MARKETS, OUTPUT_DIR, BASE_DIR, STALE_AFTER_DAYS  # Markets, folders, and the freshness limit
from eia import fetch_spot, fetch_wti_futures_history  # EIA downloads: spot prices and WTI futures history
from futures import download_contracts, curve_on, save_snapshot, front_month_continuous, SNAPSHOT_FILE  # Yahoo downloads and the snapshot store
from spreads import curve_spreads, brent_wti_spot, dated_brent_vs_future, wti_m1m2_percentile  # The calculations
from charts import save_all_charts                 # Draws and saves all four charts

README_FILE = BASE_DIR / "README.md"               # The project's front page on GitHub
README_START = "<!-- LATEST-NUMBERS:START -->"     # Marker before the auto-updated section (hidden when GitHub shows the README)
README_END = "<!-- LATEST-NUMBERS:END -->"         # Marker after it


def check_fresh(market, date):
    """Stop the run if a curve's date is too old to be today's data.

    market -- "Brent" or "WTI", for the error message
    date   -- the curve's date from futures.curve_on()
    Returns nothing if the date is within STALE_AFTER_DAYS of today.
    Exists because a download can "succeed" but return old prices (e.g. Yahoo stops updating a contract);
    saving those would put a stale curve into the history under an old date without anyone noticing.
    """
    age = (dt.date.today() - date.date()).days     # How many calendar days old the curve is
    if age > STALE_AFTER_DAYS:                     # Older than the limit in config.py...
        raise RuntimeError(                        # ...so stop with a clear message
            f"The newest complete {market} curve is from {date:%d %b %Y}, {age} days ago "  # What we found...
            f"(limit {STALE_AFTER_DAYS}). Yahoo data looks stale; nothing has been saved."  # ...and what it means
        )                                          # End of the error message


def summary_markdown(curves, spot, brent_future, wti_history, chart_paths, run_time, image_folder=""):
    """Write today's numbers as Markdown: one table with a date beside every number, then the charts, then notes.

    curves       -- dictionary of market -> (curve, date) from futures.curve_on()
    spot         -- the table from eia.fetch_spot()
    brent_future -- the Series from futures.front_month_continuous("Brent")
    wti_history  -- the table from eia.fetch_wti_futures_history()
    chart_paths  -- the saved chart files from charts.save_all_charts()
    run_time     -- when this run happened, to stamp the summary
    image_folder -- what to put in front of each chart's file name: "" for output/summary.md (the charts
                    sit next to it) and "output/" for README.md (which sits one folder up)
    Returns the section as one string (no title, so it can go into both summary.md and the README).
    Markdown is plain text with light formatting (| separates table columns, # marks a heading)
    that VS Code and GitHub display as a neat table. The numbers come from the same spreads.py
    functions that `python spreads.py` uses, so the two can never disagree.
    """
    table = curve_spreads(curves)                  # Both markets' M1-M2, M1-M6, M1-M12, each with its curve's date
    bw = brent_wti_spot(spot)                      # Brent-WTI spot spread on EIA's latest day with both prices
    db = dated_brent_vs_future(spot, brent_future) # Dated Brent minus the front-month future, on the latest shared date
    is_wti_m1m2 = (table["market"] == "WTI") & (table["spread"] == "M1-M2")  # Find the WTI M1-M2 row
    wti_today = table.loc[is_wti_m1m2, "value"].iloc[0]  # Its value
    wti_date = curves["WTI"][1]                    # The date of the WTI curve it came from
    pct = wti_m1m2_percentile(wti_today, wti_history)  # Where it sits in the 2010-2024 EIA history

    lines = [                                      # The section is built up here, one line at a time
        f"Run at {run_time:%d %b %Y %H:%M} UK time. Prices in $/bbl. "  # When it ran and the units...
        "Every row shows the date its prices come from.",  # ...and the date rule
        "",                                        # Blank line (Markdown needs these between blocks)
        "### Today's numbers",                     # Sub-heading
        "",                                        # Blank line
        "| Measure | Value | Reading | Data date | Working |",  # Table header row
        "|---|---:|---|---|---|",                  # Divider row; ---: right-aligns the Value column so decimals line up
    ]

    for _, row in table.iterrows():                # One table row per time spread
        lines.append(f"| {row['market']} {row['spread']} | {row['value']:+.2f} | {row['structure']} | "  # e.g. "Brent M1-M2 | +4.21 | backwardation"
                     f"{row['date']:%d %b %Y} | {row['contracts']} |")  # ...the curve's date and the contracts subtracted

    lines.append(f"| Brent-WTI spot spread (EIA) | {bw['spread']:+.2f} | location spread | "  # Brent-WTI spot row...
                 f"{bw['date']:%d %b %Y} | Brent {bw['brent']:.2f} minus WTI {bw['wti']:.2f} |")  # ...its date and the working

    db_reading = "spot above future" if db["spread"] > 0 else "spot below future"  # Plain-English reading of the sign
    lines.append(f"| Dated Brent minus front-month future | {db['spread']:+.2f} | {db_reading} | "  # Dated Brent row...
                 f"{db['date']:%d %b %Y} (latest date both sources have) | "  # ...its shared date (two sources)...
                 f"EIA {db['dated_brent']:.2f} minus Yahoo BZ=F {db['front_future']:.2f} |")  # ...and the working

    lines.append(f"| WTI M1-M2 percentile vs EIA history | {pct['percentile']:.1f} | percentile (not $/bbl) | "  # Percentile row...
                 f"today {wti_date:%d %b %Y}; history {pct['start']:%d %b %Y} to {pct['end']:%d %b %Y} | "  # ...today's date and the history's range...
                 f"{pct['at_or_below']:,} of {pct['days']:,} days at or below {wti_today:+.2f} |")  # ...and the count behind it

    lines += ["", "### Charts", ""]                # Charts sub-heading, with blank lines around it
    for path in chart_paths:                       # Each saved chart in turn
        lines.append(f"![{path.stem}]({image_folder}{path.name})")  # Markdown image, e.g. ![curves](output/curves.png)
        lines.append("")                           # Blank line so each chart sits on its own

    lines += [                                     # Notes on reading the numbers
        "### Notes",                               # Sub-heading
        "",                                        # Blank line
        "- Brent and WTI curves can come from different days: each uses its latest day with all 12 contracts priced.",  # curve_on() behaviour
        "- If this ran during US trading hours, the latest futures prices are live rather than closing prices.",  # Yahoo live-price caveat
        "- EIA spot prices run a few days behind; the WTI percentile deliberately compares today with 2010-2024.",  # EIA lag and the agreed exception
    ]
    return "\n".join(lines) + "\n"                 # Join into one string, ending with a newline


def update_readme(section):
    """Replace the auto-updated part of README.md with today's section, leaving everything else untouched.

    section -- the Markdown from summary_markdown(), with image_folder="output/"
    Returns nothing. Only the text between README_START and README_END is replaced, so the rest
    of the README (setup steps, file list) stays exactly as written by hand.
    """
    text = README_FILE.read_text(encoding="utf-8") # The whole README as it is now
    if README_START not in text or README_END not in text:  # Both markers must be there...
        raise RuntimeError(f"README.md is missing the {README_START} / {README_END} markers.")  # ...or we'd overwrite the wrong part
    before = text.split(README_START)[0]           # Everything above the start marker
    after = text.split(README_END)[1]              # Everything below the end marker
    new_text = before + README_START + "\n\n" + section + "\n" + README_END + after  # Rebuild with today's section in the middle
    README_FILE.write_text(new_text, encoding="utf-8")  # Save it


def main():
    """Run the tracker from start to finish.

    Takes no inputs (all settings live in config.py) and returns nothing.
    Everything is downloaded and checked first; files are only written once every check has passed.
    Any failure raises an error, which makes Python exit with a failure code. That's what tells
    GitHub Actions to stop before its commit step.
    """
    run_time = dt.datetime.now()                   # Note when this run started, for the summary
    print("Downloading futures curves from Yahoo Finance...")  # Progress message; downloads take a little while
    curves = {}                                    # market -> (curve, date) gets collected here
    prices = {}                                    # market -> price table, kept for the charts
    for market in MARKETS:                         # "Brent" then "WTI"
        prices[market] = download_contracts(market)  # Daily closes of every live contract (stops if too few came back)
        curve, date = curve_on(prices[market])     # The latest complete curve and its date (stops if a month is missing)
        check_fresh(market, date)                  # Stop if that date is too old to be today's data
        curves[market] = (curve, date)             # Keep it; it's only saved once everything else has worked

    print("Downloading EIA spot prices and WTI futures history...")  # Progress message
    spot = fetch_spot()                            # EIA Brent and WTI spot prices since 2010 (stops on a bad key or outage)
    brent_future = front_month_continuous("Brent") # Yahoo's continuous Brent front-month series (stops if empty)
    wti_history = fetch_wti_futures_history()      # EIA WTI contracts 1-4, 2010 to April 2024

    print("Making charts and writing the summary...")  # Progress message
    chart_paths = save_all_charts(curves, prices, spot, wti_history)  # Draw and save all four charts
    file_section = summary_markdown(curves, spot, brent_future, wti_history, chart_paths, run_time)  # Charts linked from output/
    readme_section = summary_markdown(curves, spot, brent_future, wti_history, chart_paths, run_time, "output/")  # Charts linked from the top folder
    summary_path = OUTPUT_DIR / "summary.md"       # Where the summary goes
    summary_path.write_text("# Oil Curve Tracker summary\n\n" + file_section, encoding="utf-8")  # Save it with a title
    update_readme(readme_section)                  # Refresh the README's "Latest numbers" section

    for market, (curve, date) in curves.items():   # Every check has passed, so now it's safe to...
        save_snapshot(market, date, curve)         # ...add each curve to the daily history

    print()                                        # A blank line to separate the results from any download warnings
    print(file_section)                            # Show the summary on screen too
    print(f"Summary saved to   {summary_path}")    # Where each output went
    print(f"README updated     {README_FILE}")     # The README
    for path in chart_paths:                       # Each chart image in turn
        print(f"Chart saved to     {path}")        # Where it went
    print(f"Snapshots added to {SNAPSHOT_FILE}")   # The daily curve history


if __name__ == "__main__":                         # Only runs when you type "python main.py", not when imported
    main()                                         # Run the tracker
