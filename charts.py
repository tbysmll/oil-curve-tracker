"""
charts.py - draws the tracker's five dashboard charts and saves them as PNG files in docs/charts/.
(They live inside docs/ because GitHub Pages can only show files in that folder; the README
and output/summary.md link to the same files, so each chart is stored once.)

  1. curves.png                 - today's Brent and WTI curves, each against the same contracts one month earlier
  2. brent_wti_spread.png       - the Brent-WTI spot spread (EIA) over the past two years
  3. m1_m6_fixed.png            - today's M1 minus M6 contracts, held fixed, over the past six months
  4. wti_m1m2_history.png       - a histogram of WTI M1-M2 from EIA history (2010-2024), with today's value marked
  5. front_month_comparison.png - Brent and WTI front-month futures over the past year, and the gap between them

Each image is a compact "card chart" in the house style (chart_style.py): just the plot. Each plot function
returns a dictionary with the file plus its numbered takeaway title (generated from the data), subtitle,
source and any note, which report.py places in the dashboard card around the image.
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

# The warning shown under Figure 5 on the dashboard and in the README
ROLL_NOTE = ("Continuous front-month series switch to the next contract on roll days, "  # What they are...
             "so a sudden jump on those days isn't a real price move.")  # ...and why a jump can mislead


def chart_info(path, number, title, subtitle, source, note=""):
    """Bundle everything the dashboard needs to show one chart.

    path     -- the saved PNG
    number   -- the figure number, e.g. 1
    title    -- the takeaway title, generated from the data
    subtitle -- what's plotted and the units
    source   -- the source line, including the data date(s)
    note     -- an optional warning or explanation shown under the chart
    Returns a dictionary with those six entries, under the keys path, number, title, subtitle, source and note.
    """
    return {"path": path, "number": number, "title": title,  # The file, its number and its takeaway...
            "subtitle": subtitle, "source": source, "note": note}  # ...and the text that goes around it


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
    """Figure 1 (full width): each market's curve today (solid) against the same contracts one month earlier (dashed).

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    Returns the chart's details from chart_info().
    One panel per market, side by side on the same price scale, with a gold dot on today's front month (M1).
    """
    with plt.rc_context(style.rc_params()):        # Apply the house style only while this chart is drawn
        fig, axes = style.new_figure(1, len(curves), size=style.WIDE_SIZE, sharey=True)  # Two panels sharing one price scale

        for i, (ax, (market, (curve, date))) in enumerate(zip(axes, curves.items())):  # Each panel with its market (i = 0, 1)
            colour = style.MARKET_COLOURS[market]  # Navy for Brent, mid blue for WTI
            earlier, earlier_date = same_contracts_earlier(prices[market], curve, date)  # Same contracts a month ago
            x = list(range(len(curve)))            # x positions 0-11, one per delivery month

            ax.plot(x, earlier.values, color=style.DARK_GREY, linewidth=1.2, linestyle="--",  # A month earlier: thin grey dashes
                    label=f"{earlier_date:%d %b}") # Named by its date in the key
            ax.plot(x, curve.values, color=colour, label=f"{date:%d %b}")  # Today: solid, in the market's colour, named by its date
            style.mark_latest(ax, 0, curve.iloc[0], f"{curve.iloc[0]:.2f}")  # Gold dot and price on today's front month (M1)

            ax.set_xticks(x[::2])                  # A tick on every other contract, so the labels don't crowd
            ax.set_xticklabels([month_label(c) for c in curve.index[::2]])  # "Jan-27", "Mar-27" ...
            ax.set_xlim(-0.5, x[-1] + 0.5)         # A little space before M1 and after M12
            ax.set_title(market, loc="left", fontsize=9, fontweight="bold", color=colour, pad=16)  # Panel name, above the key
            style.add_key(ax)                      # "02 Oct - - -   02 Nov ——" above each panel
            if i == 0:                             # The left panel shares the right panel's scale...
                ax.tick_params(labelright=False)   # ...so it doesn't repeat the numbers in the gap between panels

        path = style.save(fig, CHART_DIR / "curves.png")  # Save the image

    as_of = ", ".join(f"{date:%d %b %Y} ({market})" for market, (_, date) in curves.items())  # Each curve's own date
    return chart_info(path, 1, curves_takeaway(curves),  # The takeaway title, from the data
                      "Futures price by delivery month, $/bbl: latest (solid) vs the same contracts one month earlier (dashed)",  # Subtitle
                      f"NYMEX via Yahoo Finance. Data as of {as_of}.")  # Source line


def plot_brent_wti_spread(spot, years=2):
    """Figure 2: the Brent-WTI spot spread from EIA over the past `years` years, with its median as a reference line.

    spot  -- the table from eia.fetch_spot()
    years -- how many years back from EIA's latest date to show
    Returns the chart's details from chart_info(). The title says whether the spread rose or fell over the past month.
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
        takeaway = f"Brent-WTI spot spread {verb} {abs(change):.2f} $/bbl over the past month, to {latest:+.2f}"  # e.g. "...down 11.05..."

    with plt.rc_context(style.rc_params()):        # Apply the house style while this chart is drawn
        fig, ax = style.new_figure()               # One half-width card
        ax.axhline(0, color=style.LIGHT_GREY, linewidth=1)  # Zero line: below it, WTI would be dearer than Brent
        ax.plot(recent.index, [median] * len(recent), color=style.DARK_GREY, linewidth=1, linestyle="--",  # Two-year median...
                label="2-yr median")               # ...as a dashed reference line, named in the key
        ax.plot(recent.index, recent.values, color=style.NAVY, linewidth=1.3, label="Brent minus WTI")  # The daily spread

        style.mark_last(ax, recent.index[-1], latest)  # Gold dot on today's value
        nudges = style.label_offsets(ax, [latest, median])  # Stop the two tags overlapping
        style.value_tag(ax, latest, f"{latest:+.2f}", style.NAVY, dy=nudges[0])  # Today's value on the axis
        style.value_tag(ax, median, f"{median:+.2f}", style.DARK_GREY, dy=nudges[1])  # The median on the axis
        style.hide_numbers_under_tags(ax, [latest, median], nudges)  # Hide axis numbers the tags would cover
        style.add_key(ax)                          # Small key above the plot
        style.format_dates(ax)                     # "Nov-26" dates
        path = style.save(fig, CHART_DIR / "brent_wti_spread.png")  # Save the image

    return chart_info(path, 2, takeaway,           # The takeaway title, from the data
                      "Daily Brent (Dated, FOB) minus WTI (Cushing) spot price, $/bbl",  # Subtitle
                      f"EIA. Data as of {end:%d %b %Y}.")  # Source line


def plot_fixed_m1_m6(curves, prices, months=6):
    """Figure 3: today's M1 contract minus today's M6 contract, held fixed, over the past `months` months.

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    months -- how many months of history to show
    Returns the chart's details from chart_info(). The title says whether each six-month spread rose or fell on the month.
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
        fig, ax = style.new_figure()               # One half-width card
        ax.axhline(0, color=style.LIGHT_GREY, linewidth=1)  # Zero line: above = backwardation, below = contango
        for market, (series, _, _, _) in lines.items():  # One line per market
            ax.plot(series.index, series.values, color=style.MARKET_COLOURS[market], label=market)  # Navy / mid blue, named in the key

        latest = [series.iloc[-1] for series, _, _, _ in lines.values()]  # Each line's latest value
        nudges = style.label_offsets(ax, latest)   # Stop the two tags overlapping
        for (market, (series, _, _, _)), dy in zip(lines.items(), nudges):  # Each line in turn
            style.mark_last(ax, series.index[-1], series.iloc[-1])  # Gold dot on its latest point
            style.value_tag(ax, series.iloc[-1], f"{series.iloc[-1]:+.2f}", style.MARKET_COLOURS[market], dy=dy)  # Its value on the axis
        style.hide_numbers_under_tags(ax, latest, nudges)  # Hide axis numbers the tags would cover
        style.add_key(ax)                          # Small key above the plot
        style.format_dates(ax)                     # "Jun-26" dates
        path = style.save(fig, CHART_DIR / "m1_m6_fixed.png")  # Save the image

    contracts = "; ".join(f"{m} {month_label(n)} minus {month_label(f)}" for m, (_, n, f, _) in lines.items())  # Which contracts
    as_of = ", ".join(f"{d:%d %b %Y} ({m})" for m, (_, _, _, d) in lines.items())  # Each market's own date
    return chart_info(path, 3, takeaway,           # The takeaway title, from the data
                      f"Daily spread between today's M1 and M6 contracts, held fixed ({contracts}), $/bbl",  # Subtitle
                      f"NYMEX via Yahoo Finance. Data as of {as_of}.")  # Source line


def plot_wti_m1m2_histogram(curves, wti_history):
    """Figure 4: how often each WTI M1-M2 value occurred in EIA's 2010-2024 history, with today's value marked.

    curves      -- dictionary of market -> (curve, date) from futures.curve_on() (only WTI is used)
    wti_history -- the table from eia.fetch_wti_futures_history()
    Returns the chart's details from chart_info().
    The few most extreme contango days (e.g. -58.06 in April 2020) would squash every other bar into
    a thin spike, so the lowest 0.5% of days are left off the chart and the note says how many.
    """
    hist = wti_m1m2_history(wti_history)           # Daily WTI M1-M2, 2010 to April 2024
    curve, date = curves["WTI"]                    # Today's WTI curve and its date
    today = time_spreads(curve).set_index("spread").loc["M1-M2", "value"]  # Today's WTI M1-M2, same calculation as spreads.py
    pct = wti_m1m2_percentile(today, wti_history)  # Its percentile and the history's details

    lower = hist.quantile(0.005)                   # Left edge of the chart: the value only 0.5% of days fell below
    upper = max(hist.max(), today) + 0.25          # Right edge: the highest value (history or today) plus a margin
    off_chart = int((hist < lower).sum())          # How many days are left off on the left

    with plt.rc_context(style.rc_params()):        # Apply the house style while this chart is drawn
        fig, ax = style.new_figure()               # One half-width card
        ax.hist(hist, bins=50, range=(lower, upper),  # Count days in 50 equal-width ranges between the edges
                color=style.MID_BLUE, edgecolor=style.WHITE, linewidth=0.4)  # WTI's colour, thin white gaps between bars
        ax.axvline(today, color=style.GOLD, linewidth=1.8)  # Today's value as a gold vertical line
        ax.annotate(f"Latest {today:+.2f}",        # Label today's line with its value...
                    xy=(today, 1), xycoords=("data", "axes fraction"),  # ...at the top of the line (x in $/bbl, y as a fraction of the height)
                    xytext=(4, -2), textcoords="offset points",  # ...just to the right
                    ha="left", va="top", fontsize=8, fontweight="bold", color=style.DARK_GREY)  # Bold grey text
        ax.set_xlabel("WTI M1-M2 spread, $/bbl", fontsize=8)  # Here $/bbl runs along the bottom; the height counts days
        path = style.save(fig, CHART_DIR / "wti_m1m2_history.png")  # Save the image

    return chart_info(path, 4,                     # Figure 4...
                      f"WTI M1-M2 at {today:+.2f} $/bbl: at or above {pct['percentile']:.1f}% of days in 2010-24",  # ...takeaway title
                      f"Number of days at each WTI M1-M2 spread, {pct['start']:%b-%y} to {pct['end']:%b-%y} "  # Subtitle: what's plotted...
                      f"({pct['days']:,} days); gold line = latest value",  # ...and what the gold line is
                      f"EIA (history to {pct['end']:%d %b %Y}), NYMEX via Yahoo Finance (latest, {date:%d %b %Y}).",  # Two sources, two dates
                      f"{off_chart} days below {lower:+.2f} $/bbl not shown "  # Note: what was cut off...
                      f"(lowest {pct['min']:+.2f} on {pct['min_date']:%d %b %Y}).")  # ...and the extreme it hides


def plot_front_month_comparison(brent_front, wti_front, years=1):
    """Figure 5: Brent and WTI front-month futures over the past `years` years (top) and Brent minus WTI (bottom).

    brent_front -- the Series from futures.front_month_continuous("Brent") (Yahoo's BZ=F)
    wti_front   -- the Series from futures.front_month_continuous("WTI") (Yahoo's CL=F)
    years       -- how many years back from the latest shared date to show
    Returns the chart's details from chart_info(). The title says how the spread has moved over the year.
    Two panels stacked on one shared date axis, so each spread value sits directly under the two prices it comes from.
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
            top.plot(recent.index, recent[column], color=style.MARKET_COLOURS[market], linewidth=1.3, label=market)  # Navy / mid blue
        prices_now = [recent["brent"].iloc[-1], recent["wti"].iloc[-1]]  # Latest Brent and WTI prices
        nudges = style.label_offsets(top, prices_now)  # Stop the two tags overlapping
        for (market, value), dy in zip(zip(["Brent", "WTI"], prices_now), nudges):  # Each market in turn
            style.mark_last(top, recent.index[-1], value)  # Gold dot on its latest price
            style.value_tag(top, value, f"{value:.2f}", style.MARKET_COLOURS[market], dy=dy)  # Its price on the axis
        style.hide_numbers_under_tags(top, prices_now, nudges)  # Hide axis numbers the tags would cover
        style.add_key(top)                         # Small key above the top panel

        bottom.axhline(0, color=style.LIGHT_GREY, linewidth=1)  # Zero line: above it Brent is dearer than WTI
        bottom.plot(recent.index, recent["spread"], color=style.DARK_GREY, linewidth=1.2)  # The gap (secondary series: grey)
        style.mark_last(bottom, recent.index[-1], latest)  # Gold dot on today's gap
        style.value_tag(bottom, latest, f"{latest:+.2f}", style.DARK_GREY)  # Today's gap on the axis
        style.hide_numbers_under_tags(bottom, [latest])  # Hide the axis number the tag would cover
        style.format_dates(bottom)                 # "Nov-26" dates along the bottom
        path = style.save(fig, CHART_DIR / "front_month_comparison.png")  # Save the image

    return chart_info(path, 5, takeaway,           # The takeaway title, from the data
                      "Continuous front-month futures, $/bbl (top); Brent minus WTI, $/bbl (bottom)",  # Subtitle
                      f"NYMEX via Yahoo Finance (BZ=F, CL=F). Data as of {end:%d %b %Y}.",  # Source line
                      ROLL_NOTE)                   # The roll-day warning


def save_all_charts(curves, prices, spot, wti_history, brent_front, wti_front):
    """Draw and save all five charts.

    curves      -- dictionary of market -> (curve, date) from futures.curve_on()
    prices      -- dictionary of market -> price table from futures.download_contracts()
    spot        -- the table from eia.fetch_spot()
    wti_history -- the table from eia.fetch_wti_futures_history()
    brent_front -- the Series from futures.front_month_continuous("Brent")
    wti_front   -- the Series from futures.front_month_continuous("WTI")
    Returns a list of five chart_info() dictionaries, in figure order.
    """
    return [                                       # Make each chart in turn and collect its details
        plot_curves(curves, prices),               # Figure 1: curves today vs a month earlier (full width)
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

    for chart in save_all_charts(curves, prices, spot, wti_history, brent_front, wti_front):  # Make all five charts
        print(f"Figure {chart['number']}: {chart['title']}  ->  {chart['path']}")  # Each title and where its image went
