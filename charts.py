"""
charts.py - draws the tracker's four charts and saves them as PNG files in docs/charts/.
(They live inside docs/ because GitHub Pages can only show files in that folder; the README
and output/summary.md link to the same files, so each chart is stored once.)

  1. curves.png            - today's Brent and WTI curves, each against the same contracts one month earlier
  2. brent_wti_spread.png  - the Brent-WTI spot spread (EIA) over the past two years
  3. m1_m6_fixed.png       - today's M1 minus M6 contracts, held fixed, over the past six months
  4. wti_m1m2_history.png  - a histogram of WTI M1-M2 from EIA history (2010-2024), with today's value marked

Every chart is in $/bbl and has its data date in the title (CLAUDE.md rule).
The calculations live in spreads.py; this file only draws.
Run it with:  python charts.py
"""

import pandas as pd                                # pandas, for dates and tables
import matplotlib.pyplot as plt                    # pyplot is matplotlib's drawing toolkit
import matplotlib.dates as mdates                  # Formats dates along an axis, e.g. "Jan 26"
from config import MARKETS, CHART_DIR              # Each market's colour, and where to save the charts
from spreads import (                              # The calculations behind the charts
    time_spreads,                                  # Today's M1-M2 etc. from a curve
    wti_m1m2_percentile,                           # Where today's WTI M1-M2 sits in history
    wti_m1m2_history,                              # The daily WTI M1-M2 history from EIA
    brent_wti_spot_history,                        # The daily Brent-WTI spot spread from EIA
    fixed_contract_spread,                         # The spread between two fixed contracts over time
)

INK = "#333333"          # Dark grey for lines that belong to neither market (e.g. the Brent-WTI spread)
BARS = "#b0b0b0"         # Light grey for the histogram bars, so today's marker stands out
GRID = "#dddddd"         # Very faint grey for gridlines and the zero line, so they stay in the background


def style_axes(ax):
    """Apply the shared clean style to one chart area.

    ax -- a matplotlib chart area (an "Axes")
    Returns nothing. Faint horizontal gridlines behind the data, and no top or right border.
    Exists so all four charts look the same.
    """
    ax.grid(axis="y", color=GRID, linewidth=0.8)   # Faint horizontal gridlines to help read values
    ax.set_axisbelow(True)                         # Keep the gridlines behind the data
    ax.spines[["top", "right"]].set_visible(False) # Remove the top and right border


def save(fig, filename):
    """Save a finished figure into docs/charts/ and free the memory it used.

    fig      -- the matplotlib figure to save
    filename -- the file name, e.g. "curves.png"
    Returns the full path of the saved file.
    """
    path = CHART_DIR / filename                    # Full path, e.g. docs/charts/curves.png
    fig.savefig(path, dpi=150, bbox_inches="tight")  # Save; dpi=150 keeps it sharp, "tight" trims spare white space
    plt.close(fig)                                 # Free the memory (no window is opened)
    return path                                    # Tell the caller where the file went


def month_label(contract):
    """Turn a delivery-month label like "2027-01" into "Jan 27", for axis labels and legends."""
    return pd.Timestamp(contract).strftime("%b %y")  # Read "2027-01" as 1 Jan 2027, then write it as "Jan 27"


def same_contracts_earlier(prices, curve, date, months=1):
    """The prices of the contracts on `curve`, as they stood about `months` months before `date`.

    prices -- the table from futures.download_contracts()
    curve  -- the Series from futures.curve_on() (only its contract labels are used)
    date   -- the date of that curve
    Returns a Series of earlier prices (same contracts, same order) and the actual earlier trading day.
    Uses the same 3-day gap filling as futures.curve_on(), so thin back months are treated the same way.
    """
    target = date - pd.DateOffset(months=months)   # e.g. 30 Oct -> 30 Sep
    earlier_date = prices.index[prices.index <= target].max()  # The last trading day on or before that (skips weekends)
    filled = prices.loc[:earlier_date, curve.index].ffill(limit=3)  # Same contracts; fill gaps up to 3 trading days old
    return filled.loc[earlier_date], earlier_date  # The prices on that day, and the day itself


def plot_curves(curves, prices):
    """Chart 1: each market's curve today (solid) against the same contracts one month earlier (dashed).

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    Returns the path of the saved PNG.
    One panel per market, side by side, so each panel's title can carry its own date.
    """
    fig, axes = plt.subplots(1, len(curves), figsize=(13, 5.5), sharey=True)  # Two panels sharing one price scale

    for ax, (market, (curve, date)) in zip(axes, curves.items()):  # Pair each panel with a market
        colour = MARKETS[market]["colour"]         # This market's colour from config.py
        earlier, earlier_date = same_contracts_earlier(prices[market], curve, date)  # Same contracts a month ago
        x = range(len(curve))                      # x positions 0-11, one per delivery month
        ax.plot(x, curve.values, color=colour, linewidth=2,  # Today's curve: solid line...
                marker="o", markersize=6, label=f"{date:%d %b %Y}")  # ...with a dot per contract, labelled with its date
        ax.plot(x, earlier.values, color=colour, linewidth=2, linestyle="--",  # A month earlier: dashed line...
                marker="o", markersize=5, markerfacecolor="white",  # ...with hollow dots so it reads as the "older" line
                label=f"{earlier_date:%d %b %Y} (one month earlier)")  # Labelled with its own date
        ax.set_xticks(list(x))                     # One tick per contract
        ax.set_xticklabels([month_label(c) for c in curve.index], rotation=45, ha="right")  # "Dec 26", "Jan 27" ... slanted to fit
        ax.set_xlabel("Delivery month")            # Explain the x-axis
        ax.set_title(f"{market} futures curve, {date:%d %b %Y}")  # Title with the data date
        style_axes(ax)                             # Shared clean style
        ax.legend(frameon=False)                   # Legend without a box

    axes[0].set_ylabel("Price ($/bbl)")            # Only the left panel needs the y label (the scale is shared)
    return save(fig, "curves.png")                 # Save and return the path


def plot_brent_wti_spread(spot, years=2):
    """Chart 2: the Brent-WTI spot spread from EIA over the past `years` years.

    spot  -- the table from eia.fetch_spot()
    years -- how many years back from EIA's latest date to show
    Returns the path of the saved PNG.
    """
    spread = brent_wti_spot_history(spot)          # Daily Brent minus WTI, every day both exist
    end = spread.index.max()                       # EIA's latest day with both prices
    recent = spread.loc[end - pd.DateOffset(years=years):]  # Just the last two years

    fig, ax = plt.subplots(figsize=(10, 5))        # One chart, 10 x 5 inches
    ax.axhline(0, color=GRID, linewidth=1)         # A zero line, so you can see if Brent ever fell below WTI
    ax.plot(recent.index, recent.values, color=INK, linewidth=1.5)  # The daily spread
    ax.annotate(f"{recent.iloc[-1]:+.2f}",         # Label only the latest value
                (recent.index[-1], recent.iloc[-1]),  # The point being labelled: the last day
                textcoords="offset points", xytext=(6, 0), va="center", fontsize=9)  # Just to its right
    ax.set_title(f"Brent minus WTI spot price (EIA), {recent.index[0]:%d %b %Y} to {end:%d %b %Y}")  # Title with the date range
    ax.set_ylabel("Spread ($/bbl)")                # Explain the y-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))  # Dates along the bottom as "Jan 26"
    style_axes(ax)                                 # Shared clean style
    return save(fig, "brent_wti_spread.png")       # Save and return the path


def plot_fixed_m1_m6(curves, prices, months=6):
    """Chart 3: today's M1 contract minus today's M6 contract, held fixed, over the past `months` months.

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    months -- how many months of history to show
    Returns the path of the saved PNG.
    """
    fig, ax = plt.subplots(figsize=(10, 5))        # One chart, 10 x 5 inches
    ax.axhline(0, color=GRID, linewidth=1)         # A zero line: above = backwardation, below = contango
    end_dates = []                                 # Each market's end date, for the title

    for market, (curve, date) in curves.items():   # "Brent" then "WTI"
        near, far = curve.index[0], curve.index[5] # Today's M1 and M6 contracts, e.g. "2026-12" and "2027-05"
        spread = fixed_contract_spread(prices[market], near, far, date, months)  # Their daily spread over six months
        ax.plot(spread.index, spread.values, color=MARKETS[market]["colour"], linewidth=2,  # One line per market
                label=f"{market}: {month_label(near)} minus {month_label(far)}")  # Legend names the two fixed contracts
        ax.annotate(f"{spread.iloc[-1]:+.2f}",     # Label only the latest value
                    (spread.index[-1], spread.iloc[-1]),  # The point being labelled: the last day
                    textcoords="offset points", xytext=(6, 0), va="center", fontsize=9)  # Just to its right
        end_dates.append(f"{market} to {date:%d %b %Y}")  # e.g. "Brent to 30 Oct 2026"

    ax.set_title("Today's M1 minus M6 contracts, held fixed, past six months\n"  # Title line 1: what's shown
                 + "; ".join(end_dates))           # Title line 2: each market's data date
    ax.set_ylabel("Spread ($/bbl)")                # Explain the y-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))  # Dates along the bottom as "Jun 26"
    style_axes(ax)                                 # Shared clean style
    ax.legend(frameon=False)                       # Legend without a box
    return save(fig, "m1_m6_fixed.png")            # Save and return the path


def plot_wti_m1m2_histogram(curves, wti_history):
    """Chart 4: how often each WTI M1-M2 value occurred in EIA's 2010-2024 history, with today's value marked.

    curves      -- dictionary of market -> (curve, date) from futures.curve_on() (only WTI is used)
    wti_history -- the table from eia.fetch_wti_futures_history()
    Returns the path of the saved PNG.
    The few most extreme contango days (e.g. -58.06 in April 2020) would squash every other bar into
    a thin spike, so the lowest 0.5% of days are left off the chart and a note says how many.
    """
    hist = wti_m1m2_history(wti_history)           # Daily WTI M1-M2, 2010 to April 2024
    curve, date = curves["WTI"]                    # Today's WTI curve and its date
    today = time_spreads(curve).set_index("spread").loc["M1-M2", "value"]  # Today's WTI M1-M2, same calculation as spreads.py
    pct = wti_m1m2_percentile(today, wti_history)  # Its percentile and the history's details

    lower = hist.quantile(0.005)                   # Left edge of the chart: the value only 0.5% of days fell below
    upper = max(hist.max(), today) + 0.25          # Right edge: the highest value (history or today) plus a margin
    off_chart = int((hist < lower).sum())          # How many days are left off on the left

    fig, ax = plt.subplots(figsize=(10, 5))        # One chart, 10 x 5 inches
    ax.hist(hist, bins=60, range=(lower, upper),   # Count days in 60 equal-width ranges between the edges
            color=BARS, edgecolor="white", linewidth=0.5)  # Grey bars with thin white gaps between them
    ax.axvline(today, color=MARKETS["WTI"]["colour"], linewidth=2)  # A vertical line at today's value, in WTI's colour
    ax.text(today + 0.08, 0.95,                    # Label just to the right of the line, near the top...
            f"Today ({date:%d %b %Y}): {today:+.2f}\npercentile {pct['percentile']:.1f}",  # ...with the value, date and percentile
            transform=ax.get_xaxis_transform(),    # x is measured in $/bbl, y as a fraction of the chart height
            ha="left", va="top", fontsize=9)       # Text starts at that point and hangs down from it
    ax.text(0.99, 0.70,                            # A small note on the right, below today's label...
            f"{off_chart} days below {lower:+.2f} not shown\n(lowest {pct['min']:+.2f} on {pct['min_date']:%d %b %Y})",  # ...saying what was cut off
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#666666")  # Positioned relative to the chart area
    ax.set_title(f"WTI M1-M2 spread, EIA daily history {pct['start']:%d %b %Y} to {pct['end']:%d %b %Y} "  # Title: history dates...
                 f"({pct['days']:,} days)\nvs today's value from {date:%d %b %Y}")  # ...and today's data date
    ax.set_xlabel("WTI M1-M2 spread ($/bbl)")      # Explain the x-axis
    ax.set_ylabel("Number of days")                # Explain the y-axis
    style_axes(ax)                                 # Shared clean style
    return save(fig, "wti_m1m2_history.png")       # Save and return the path


def save_all_charts(curves, prices, spot, wti_history):
    """Draw and save all four charts.

    curves      -- dictionary of market -> (curve, date) from futures.curve_on()
    prices      -- dictionary of market -> price table from futures.download_contracts()
    spot        -- the table from eia.fetch_spot()
    wti_history -- the table from eia.fetch_wti_futures_history()
    Returns a list of the four saved file paths.
    """
    return [                                       # Make each chart in turn and collect where it was saved
        plot_curves(curves, prices),               # 1. Curves today vs a month earlier
        plot_brent_wti_spread(spot),               # 2. Brent-WTI spot spread, two years
        plot_fixed_m1_m6(curves, prices),          # 3. Fixed M1-M6 contracts, six months
        plot_wti_m1m2_histogram(curves, wti_history),  # 4. WTI M1-M2 histogram
    ]


if __name__ == "__main__":                         # Only runs when you type "python charts.py", not when imported
    from eia import fetch_spot, fetch_wti_futures_history  # EIA downloads (only this test block needs them)
    from futures import download_contracts, curve_on  # Yahoo downloads

    curves = {}                                    # market -> (curve, date) gets collected here
    prices = {}                                    # market -> price table gets collected here
    for market in MARKETS:                         # "Brent" then "WTI"
        prices[market] = download_contracts(market)  # Daily closes of every live contract
        curves[market] = curve_on(prices[market])  # The latest complete curve and its date
    spot = fetch_spot()                            # EIA Brent and WTI spot prices since 2010
    wti_history = fetch_wti_futures_history()      # EIA WTI contracts 1-4, 2010 to April 2024

    for path in save_all_charts(curves, prices, spot, wti_history):  # Make all four charts
        print(f"Saved {path}")                     # Say where each one went
