"""
main.py - runs the whole tracker once: download, check, calculate, chart, write the reports, save today's curves.

Run it with:  python main.py
It writes:
  data/curve_snapshots.csv  - today's Brent and WTI curves added to the daily history
  output/summary.md         - a table of today's numbers, each with the date its prices come from, plus the charts
  docs/charts/*.png         - the four charts (see charts.py)
  docs/index.html           - the web report published by GitHub Pages, with Toby's commentary (see report.py)
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
from charts import save_all_charts                 # Draws and saves all four charts
from report import summary_rows, summary_markdown, write_html  # Turns the results into the table, Markdown and web page

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


def update_readme(section):
    """Replace the auto-updated part of README.md with today's section, leaving everything else untouched.

    section -- the Markdown from report.summary_markdown(), with image_folder="docs/charts/"
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
    run_time = dt.datetime.now()                   # Note when this run started, for the reports
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

    print("Making charts and writing the reports...")  # Progress message
    chart_paths = save_all_charts(curves, prices, spot, wti_history)  # Draw and save all four charts into docs/charts/
    rows = summary_rows(curves, spot, brent_future, wti_history)  # Today's numbers as table rows, built once for all three reports
    file_section = summary_markdown(rows, chart_paths, run_time, "../docs/charts/")  # For output/summary.md (one folder down)
    readme_section = summary_markdown(rows, chart_paths, run_time, "docs/charts/")   # For README.md (top folder)
    summary_path = OUTPUT_DIR / "summary.md"       # Where the Markdown summary goes
    summary_path.write_text("# Oil Curve Tracker summary\n\n" + file_section, encoding="utf-8")  # Save it with a title
    update_readme(readme_section)                  # Refresh the README's "Latest numbers" section
    report_path = write_html(rows, chart_paths, run_time)  # Write the web report, docs/index.html

    for market, (curve, date) in curves.items():   # Every check has passed, so now it's safe to...
        save_snapshot(market, date, curve)         # ...add each curve to the daily history

    print()                                        # A blank line to separate the results from any download warnings
    print(file_section)                            # Show the summary on screen too
    print(f"Summary saved to   {summary_path}")    # Where each output went
    print(f"Web report saved   {report_path}")     # The web page
    print(f"README updated     {README_FILE}")     # The README
    for path in chart_paths:                       # Each chart image in turn
        print(f"Chart saved to     {path}")        # Where it went
    print(f"Snapshots added to {SNAPSHOT_FILE}")   # The daily curve history


if __name__ == "__main__":                         # Only runs when you type "python main.py", not when imported
    main()                                         # Run the tracker
