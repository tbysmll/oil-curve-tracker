"""
charts.py - draws the tracker's five charts and saves them as PNG files in docs/charts/.
(They live inside docs/ because GitHub Pages can only show files in that folder; the README
and output/summary.md link to the same files, so each chart is stored once.)

  1. curves.png                 - today's Brent and WTI curves, each against the same contracts one month earlier
  2. brent_wti_spread.png       - the Brent-WTI spot spread (EIA) over the past two years
  3. m1_m6_fixed.png            - today's M1 minus M6 contracts, held fixed, over the past six months
  4. wti_m1m2_history.png       - a histogram of WTI M1-M2 from EIA history (2010-2024), with today's value marked
  5. front_month_comparison.png - Brent and WTI front-month futures over the past year, and the gap between them

Every chart follows the house style in chart_style.py (bank research-note look): a numbered title that
states the takeaway (generated from the data), a subtitle with what's plotted and the units, lines
labelled at their right-hand end, today's value as a gold dot, and a source line with the data date.
The calculations live in spreads.py; this file only draws.
Run it with:  python charts.py
"""

import pandas as pd                                # pandas, for dates and tables
import matplotlib.pyplot as plt                    # pyplot is matplotlib's drawing toolkit
from config import MARKETS, CHART_DIR, NEUTRAL_BAND  # Market names, where to save the charts, and the "flat" band
import chart_style as style                        # The house style (colours, fonts, layout, labels); "style." for short
from spreads import (                              # The calculations behind the charts
    time_spreads,                                  # Today's M1-M2 etc. from a curve
    wti_m1m2_percentile,                           # Where today's WTI M1-M2 sits in history
    wti_m1m2_history,                              # The daily WTI M1-M2 history from EIA
    brent_wti_spot_history,                        # The daily Brent-WTI spot spread from EIA
    fixed_contract_spread,                         # The spread between two fixed contracts over time
    front_month_spread,                            # Brent and WTI front-month futures side by side, and their gap
)

# The warning printed under Figure 5, inside the image so it goes wherever the chart goes
ROLL_NOTE = ("Note: continuous front-month series switch to the next contract on roll days, "  # What they are...
             "so a sudden jump on those days isn't a real price move.")  # ...and why a jump can mislead


def month_label(contract):
    """Turn a delivery-month label like "2027-01" into "Jan-27" (the house date style), for axis labels and legends."""
    return pd.Timestamp(contract).strftime(style.DATE_FORMAT)  # Read "2027-01" as 1 Jan 2027, then write it as "Jan-27"


def value_a_month_earlier(series):
    """The series' value on the last day at least one month before its latest day.

    series -- a daily Series indexed by date, e.g. the Brent-WTI spot spread
    Returns one number. Used by the titles to say whether something rose or fell over the past month.
    """
    target = series.index.max() - pd.DateOffset(months=1)  # e.g. 27 Oct -> 27 Sep
    return series.loc[:target].iloc[-1]           # The last value on or before that day (skips weekends and holidays)


def describe_change(change):
    """Turn a change in $/bbl into "up", "down" or "little changed", using the project's NEUTRAL_BAND.

    change -- the change in $/bbl, e.g. +2.40
    Returns one of "up", "down", "little changed".
    Same $0.10 band as the flat label, so a move of a few cents isn't described as a trend.
    """
    if change > NEUTRAL_BAND:                      # Rose by more than $0.10...
        return "up"                                # ...call it "up"
    if change < -NEUTRAL_BAND:                     # Fell by more than $0.10...
        return "down"                              # ...call it "down"
    return "little changed"                        # Otherwise it hasn't really moved


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


def curves_takeaway(curves):
    """Figure 1's title: the curves' shape in words, generated from each market's M1-M12 spread.

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    Returns a sentence such as "Both curves in backwardation; Brent steeper at +19.79 $/bbl over 12 months".
    Uses the same time_spreads() and NEUTRAL_BAND labels as the numbers table, so title and table always agree.
    """
    summary = []                                   # (market, structure, M1-M12 value) for each market
    for market, (curve, date) in curves.items():   # "Brent" then "WTI"
        row = time_spreads(curve).set_index("spread").loc["M1-M12"]  # That market's M1-M12 row
        summary.append((market, row["structure"], row["value"]))  # e.g. ("Brent", "backwardation", 19.79)

    structures = {structure for _, structure, _ in summary}  # The different structures found (a set drops repeats)
    if len(structures) > 1:                        # The markets disagree, e.g. one backwardated, one in contango...
        return ", ".join(f"{market} in {structure}" for market, structure, _ in summary)  # ...so say each one
    structure = structures.pop()                   # Both agree: take the shared structure
    if structure == "flat":                        # Flat curves have no "steeper" side...
        return "Both curves flat over the next 12 months"  # ...so keep it simple

    steepest = summary[0]                          # Start by assuming the first market is the steeper one...
    for item in summary[1:]:                       # ...then check the others
        if abs(item[2]) > abs(steepest[2]):        # Bigger move over 12 months (either direction) = steeper
            steepest = item                        # Keep the steeper one
    return (f"Both curves in {structure}; {steepest[0]} steeper "  # e.g. "Both curves in backwardation; Brent steeper..."
            f"at {steepest[2]:+.2f} $/bbl over 12 months")  # "...at +19.79 $/bbl over 12 months"


def plot_curves(curves, prices):
    """Figure 1: each market's curve today (solid) against the same contracts one month earlier (dashed).

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    Returns the path of the saved PNG.
    One panel per market, side by side on the same price scale. The title is generated from the data.
    """
    with plt.rc_context(style.rc_params()):        # Apply the house style only while this chart is drawn
        fig, axes = style.new_figure(1, len(curves), sharey=True)  # Two panels side by side, sharing one price scale

        for i, (ax, (market, (curve, date))) in enumerate(zip(axes, curves.items())):  # Each panel with its market (i = 0, 1)
            colour = style.MARKET_COLOURS[market]  # Navy for Brent, mid blue for WTI
            earlier, earlier_date = same_contracts_earlier(prices[market], curve, date)  # Same contracts a month ago
            x = list(range(len(curve)))            # x positions 0-11, one per delivery month

            ax.plot(x, earlier.values, color=style.DARK_GREY, linewidth=1.5, linestyle="--")  # A month earlier: thin grey dashes
            ax.plot(x, curve.values, color=colour) # Today: solid line in the market's colour, drawn on top
            style.label_line_end(ax, x[-1], curve.iloc[-1], f"{date:%d-%b}", colour)  # Name each line at its right-hand end...
            style.label_line_end(ax, x[-1], earlier.iloc[-1], f"{earlier_date:%d-%b}", style.DARK_GREY)  # ...by its date
            style.mark_latest(ax, x[0], curve.iloc[0], f"{curve.iloc[0]:.2f}", dx=8, dy=8)  # Gold dot on today's front month (M1)

            ax.set_xticks(x[::2])                  # A tick on every other contract, so the labels don't crowd
            ax.set_xticklabels([month_label(c) for c in curve.index[::2]])  # "Jan-27", "Mar-27" ...
            ax.set_xlim(-0.5, x[-1] + 0.5)         # A little space before M1 and after M12
            ax.set_title(market, loc="left", fontsize=10, fontweight="bold", color=colour)  # Panel name, top-left
            style.style_axes(ax, ylabel="$/bbl" if i == 0 else "")  # y label on the left panel only (the scale is shared)

        style.add_titles(fig, 1, curves_takeaway(curves),  # "Figure 1: <takeaway from the data>"
                         "Futures price by delivery month, $/bbl: latest (solid) vs the same contracts one month earlier (dashed)")  # Subtitle
        as_of = ", ".join(f"{date:%d %b %Y} ({market})" for market, (_, date) in curves.items())  # Each curve's own date
        style.add_source(fig, "NYMEX via Yahoo Finance", as_of)  # "Source: ... Data as of 02 Nov 2026 (Brent), ..."
        return style.save(fig, CHART_DIR / "curves.png")  # Save at 10 x 5.5 in, 200 dpi, white background


def plot_brent_wti_spread(spot, years=2):
    """Figure 2: the Brent-WTI spot spread from EIA over the past `years` years, with its median as a reference line.

    spot  -- the table from eia.fetch_spot()
    years -- how many years back from EIA's latest date to show
    Returns the path of the saved PNG.
    The title says whether the spread rose or fell over the past month, generated from the data.
    """
    spread = brent_wti_spot_history(spot)          # Daily Brent minus WTI, every day both exist
    end = spread.index.max()                       # EIA's latest day with both prices
    recent = spread.loc[end - pd.DateOffset(years=years):]  # Just the last two years
    latest = recent.iloc[-1]                       # Today's (latest) spread
    change = latest - value_a_month_earlier(recent)  # How much it moved over the past month
    median = recent.median()                       # The typical spread over the two years, as a reference

    verb = describe_change(change)                 # "up", "down" or "little changed"
    if verb == "little changed":                   # No real move: say so plainly
        takeaway = f"Brent-WTI spot spread little changed over the past month at {latest:+.2f} $/bbl"  # e.g. "...at +19.73 $/bbl"
    else:                                          # A real move: say which way and by how much
        takeaway = f"Brent-WTI spot spread {verb} {abs(change):.2f} $/bbl over the past month, to {latest:+.2f}"  # e.g. "...up 2.40 $/bbl..."

    with plt.rc_context(style.rc_params()):        # Apply the house style while this chart is drawn
        fig, ax = style.new_figure()               # One chart area at the house size
        ax.axhline(0, color=style.LIGHT_GREY, linewidth=1)  # Zero line: below it, WTI would be dearer than Brent
        ax.plot([recent.index[0], recent.index[-1]], [median, median],  # Two-year median as a dashed reference line, ending at
                color=style.DARK_GREY, linewidth=1, linestyle="--")  # the last date so its label sits clear of it
        ax.plot(recent.index, recent.values, color=style.NAVY, linewidth=1.5)  # The daily spread (single series: navy)

        nudges = style.label_offsets(ax, [latest, median])  # Stop the two right-hand labels overlapping
        style.label_latest(ax, recent.index[-1], latest, f"{latest:+.2f}", style.NAVY, dy=nudges[0])  # Gold dot + today's value
        style.label_line_end(ax, recent.index[-1], median, f"2-yr median {median:+.2f}", style.DARK_GREY, dy=nudges[1])  # Name the dashed line
        style.style_axes(ax, dates=True)           # "$/bbl" label and "Nov-26" dates

        style.add_titles(fig, 2, takeaway,         # "Figure 2: <takeaway>"
                         "Daily Brent (Dated, FOB) minus WTI (Cushing) spot price, $/bbl; dashed line = two-year median")  # Subtitle
        style.add_source(fig, "EIA", f"{end:%d %b %Y}")  # EIA is the only source here
        return style.save(fig, CHART_DIR / "brent_wti_spread.png")  # Save and return the path


def plot_fixed_m1_m6(curves, prices, months=6):
    """Figure 3: today's M1 contract minus today's M6 contract, held fixed, over the past `months` months.

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    months -- how many months of history to show
    Returns the path of the saved PNG.
    The title says whether each market's six-month spread rose or fell over the past month.
    """
    lines = {}                                     # market -> (spread series, near contract, far contract, date)
    for market, (curve, date) in curves.items():   # "Brent" then "WTI"
        near, far = curve.index[0], curve.index[5] # Today's M1 and M6 contracts, e.g. "2027-01" and "2027-06"
        lines[market] = (fixed_contract_spread(prices[market], near, far, date, months), near, far, date)  # Daily spread, six months

    moves = {market: describe_change(series.iloc[-1] - value_a_month_earlier(series))  # "up"/"down"/"little changed"...
             for market, (series, _, _, _) in lines.items()}  # ...for each market over the past month
    if len(set(moves.values())) == 1:              # Both markets moved the same way (a set drops repeats)...
        verb = list(moves.values())[0]             # ...so describe them together
        if verb == "little changed":               # "both little changed" reads badly...
            how = "little changed"                 # ...so just "little changed"
        else:                                      # Otherwise...
            how = f"both {verb}"                   # ...e.g. "both down"
        values = ", ".join(f"{m} {s.iloc[-1]:+.2f}" for m, (s, _, _, _) in lines.items())  # "Brent +11.71, WTI +8.75"
        takeaway = f"Six-month spreads {how} on the month: {values} $/bbl"  # The full title
    else:                                          # They moved differently...
        takeaway = "Six-month spreads: " + ", ".join(f"{m} {moves[m]} on the month" for m in lines)  # ...so say each one

    with plt.rc_context(style.rc_params()):        # Apply the house style while this chart is drawn
        fig, ax = style.new_figure()               # One chart area at the house size
        ax.axhline(0, color=style.LIGHT_GREY, linewidth=1)  # Zero line: above = backwardation, below = contango
        for market, (series, _, _, _) in lines.items():  # One line per market
            ax.plot(series.index, series.values, color=style.MARKET_COLOURS[market])  # Navy for Brent, mid blue for WTI

        latest = [series.iloc[-1] for series, _, _, _ in lines.values()]  # Each line's latest value
        nudges = style.label_offsets(ax, latest)   # Stop the two right-hand labels overlapping
        for (market, (series, _, _, _)), dy in zip(lines.items(), nudges):  # Label each line at its end
            style.label_latest(ax, series.index[-1], series.iloc[-1],  # Gold dot on the latest point...
                               f"{market} {series.iloc[-1]:+.2f}", style.MARKET_COLOURS[market], dy=dy)  # ...with name and value
        style.style_axes(ax, dates=True)           # "$/bbl" label and "Jun-26" dates

        contracts = "; ".join(f"{m} {month_label(n)} minus {month_label(f)}" for m, (_, n, f, _) in lines.items())  # Which contracts
        style.add_titles(fig, 3, takeaway,         # "Figure 3: <takeaway>"
                         f"Daily spread between today's M1 and M6 contracts, held fixed ({contracts}), $/bbl")  # Subtitle
        as_of = ", ".join(f"{d:%d %b %Y} ({m})" for m, (_, _, _, d) in lines.items())  # Each market's own date
        style.add_source(fig, "NYMEX via Yahoo Finance", as_of)  # Source line
        return style.save(fig, CHART_DIR / "m1_m6_fixed.png")  # Save and return the path


def plot_wti_m1m2_histogram(curves, wti_history):
    """Figure 4: how often each WTI M1-M2 value occurred in EIA's 2010-2024 history, with today's value marked.

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

    takeaway = f"WTI M1-M2 at {today:+.2f} $/bbl: at or above {pct['percentile']:.1f}% of days in 2010-24"  # The percentile, in words

    with plt.rc_context(style.rc_params()):        # Apply the house style while this chart is drawn
        fig, ax = style.new_figure()               # One chart area at the house size
        ax.hist(hist, bins=60, range=(lower, upper),  # Count days in 60 equal-width ranges between the edges
                color=style.MID_BLUE, edgecolor=style.WHITE, linewidth=0.5)  # WTI's colour, thin white gaps between bars
        ax.axvline(today, color=style.GOLD, linewidth=2)  # Today's value as a gold vertical line
        ax.annotate(f"Latest {today:+.2f}\n({date:%d %b %Y})",  # Label today's line with its value and date...
                    xy=(today, 1), xycoords=("data", "axes fraction"),  # ...at the top of the line (x in $/bbl, y as a fraction of the height)
                    xytext=(6, -4), textcoords="offset points",  # ...just to the right and slightly down
                    ha="left", va="top", fontsize=9, fontweight="bold", color=style.DARK_GREY)  # Bold grey text
        ax.set_xlabel("WTI M1-M2 spread, $/bbl")   # Here $/bbl runs along the bottom...
        style.style_axes(ax, ylabel="Number of days")  # ...and the height counts days

        style.add_titles(fig, 4, takeaway,         # "Figure 4: <takeaway>"
                         f"Distribution of daily WTI M1-M2 spreads, {pct['start']:%b-%y} to {pct['end']:%b-%y} "  # Subtitle: what's plotted...
                         f"({pct['days']:,} days); gold line = latest value")  # ...and what the gold line is
        style.add_note(fig, f"Note: {off_chart} days below {lower:+.2f} $/bbl not shown "  # Say what was cut off...
                            f"(lowest {pct['min']:+.2f} on {pct['min_date']:%d %b %Y}).")  # ...and the extreme it hides
        style.add_source(fig, "EIA (history), NYMEX via Yahoo Finance (latest)",  # Two sources...
                         f"{date:%d %b %Y} (latest), {pct['end']:%d %b %Y} (history)")  # ...each with its own date
        return style.save(fig, CHART_DIR / "wti_m1m2_history.png")  # Save and return the path


def plot_front_month_comparison(brent_front, wti_front, years=1):
    """Figure 5: Brent and WTI front-month futures over the past `years` years (top) and Brent minus WTI (bottom).

    brent_front -- the Series from futures.front_month_continuous("Brent") (Yahoo's BZ=F)
    wti_front   -- the Series from futures.front_month_continuous("WTI") (Yahoo's CL=F)
    years       -- how many years back from the latest shared date to show
    Returns the path of the saved PNG.
    Two panels stacked on one shared date axis, so each spread value sits directly under the two prices
    it comes from. The title says how the spread has moved over the year.
    """
    table = front_month_spread(brent_front, wti_front)  # brent, wti and spread columns, only on days both traded
    end = table.index.max()                        # The latest day both series have
    recent = table.loc[end - pd.DateOffset(years=years):]  # Just the last year
    first, latest = recent["spread"].iloc[0], recent["spread"].iloc[-1]  # The spread a year ago and now

    verb = describe_change(latest - first)         # "up", "down" or "little changed" over the year
    if verb == "little changed":                   # No real move
        takeaway = f"Brent-WTI front-month spread little changed over the year at {latest:+.2f} $/bbl"  # Say so plainly
    else:                                          # A real move
        takeaway = f"Brent-WTI front-month spread {verb} over the year, to {latest:+.2f} $/bbl from {first:+.2f}"  # Which way, from and to

    with plt.rc_context(style.rc_params()):        # Apply the house style while this chart is drawn
        fig, (top, bottom) = style.new_figure(     # Two chart areas, one above the other...
            2, 1, sharex=True,                     # ...sharing the same dates along the bottom...
            gridspec_kw={"height_ratios": [3, 1]}) # ...with the top one three times as tall

        for market, column in [("Brent", "brent"), ("WTI", "wti")]:  # Each market's price line
            top.plot(recent.index, recent[column], color=style.MARKET_COLOURS[market], linewidth=1.5)  # Navy / mid blue
        prices_now = [recent["brent"].iloc[-1], recent["wti"].iloc[-1]]  # Latest Brent and WTI prices
        nudges = style.label_offsets(top, prices_now)  # Stop the two labels overlapping
        for (market, value), dy in zip(zip(["Brent", "WTI"], prices_now), nudges):  # Label each line at its end
            style.label_latest(top, recent.index[-1], value, f"{market} {value:.2f}",  # Gold dot, name and price...
                               style.MARKET_COLOURS[market], dy=dy)  # ...in the market's colour
        style.style_axes(top)                      # "$/bbl" label

        bottom.axhline(0, color=style.LIGHT_GREY, linewidth=1)  # Zero line: above it Brent is dearer than WTI
        bottom.plot(recent.index, recent["spread"], color=style.DARK_GREY, linewidth=1.5)  # The gap (secondary series: grey)
        style.label_latest(bottom, recent.index[-1], latest, f"{latest:+.2f}", style.DARK_GREY)  # Gold dot and today's gap
        style.style_axes(bottom, ylabel="Brent-WTI,\n$/bbl", dates=True)  # Two-line label to fit the short panel; "Nov-26" dates

        style.add_titles(fig, 5, takeaway,         # "Figure 5: <takeaway>"
                         "Continuous front-month futures, $/bbl (top); Brent minus WTI, $/bbl (bottom)")  # Subtitle
        style.add_note(fig, ROLL_NOTE)             # The roll-day warning, under the dates
        style.add_source(fig, "NYMEX via Yahoo Finance (BZ=F, CL=F)", f"{end:%d %b %Y}")  # Source line
        return style.save(fig, CHART_DIR / "front_month_comparison.png")  # Save and return the path


def save_all_charts(curves, prices, spot, wti_history, brent_front, wti_front):
    """Draw and save all five charts.

    curves      -- dictionary of market -> (curve, date) from futures.curve_on()
    prices      -- dictionary of market -> price table from futures.download_contracts()
    spot        -- the table from eia.fetch_spot()
    wti_history -- the table from eia.fetch_wti_futures_history()
    brent_front -- the Series from futures.front_month_continuous("Brent")
    wti_front   -- the Series from futures.front_month_continuous("WTI")
    Returns a list of the five saved file paths, in figure order.
    """
    return [                                       # Make each chart in turn and collect where it was saved
        plot_curves(curves, prices),               # Figure 1: curves today vs a month earlier
        plot_brent_wti_spread(spot),               # Figure 2: Brent-WTI spot spread, two years
        plot_fixed_m1_m6(curves, prices),          # Figure 3: fixed M1-M6 contracts, six months
        plot_wti_m1m2_histogram(curves, wti_history),  # Figure 4: WTI M1-M2 histogram
        plot_front_month_comparison(brent_front, wti_front),  # Figure 5: Brent vs WTI front-month futures, one year
    ]


if __name__ == "__main__":                         # Only runs when you type "python charts.py", not when imported
    from eia import fetch_spot, fetch_wti_futures_history  # EIA downloads (only this test block needs them)
    from futures import download_contracts, curve_on, front_month_continuous  # Yahoo downloads

    curves = {}                                    # market -> (curve, date) gets collected here
    prices = {}                                    # market -> price table gets collected here
    for market in MARKETS:                         # "Brent" then "WTI"
        prices[market] = download_contracts(market)  # Daily closes of every live contract
        curves[market] = curve_on(prices[market])  # The latest complete curve and its date
    spot = fetch_spot()                            # EIA Brent and WTI spot prices since 2010
    wti_history = fetch_wti_futures_history()      # EIA WTI contracts 1-4, 2010 to April 2024
    brent_front = front_month_continuous("Brent")  # Yahoo's continuous Brent front-month series (BZ=F)
    wti_front = front_month_continuous("WTI")      # Yahoo's continuous WTI front-month series (CL=F)

    for path in save_all_charts(curves, prices, spot, wti_history, brent_front, wti_front):  # Make all five charts
        print(f"Saved {path}")                     # Say where each one went
