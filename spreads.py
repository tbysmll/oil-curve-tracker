"""
spreads.py - turns the curves and price tables into the numbers the tracker reports.

The functions here never download anything themselves: they take tables in and hand results back,
so main.py can reuse them and each one can be checked on its own. Running this file directly
(python spreads.py) downloads everything and prints every result with the date it comes from.

Date rule (see CLAUDE.md): a calculation that combines two sources uses the latest date BOTH have.
A calculation within one source uses that source's own latest date.
"""

import pandas as pd                                # pandas tables
from config import NEUTRAL_BAND, CURVE_MONTHS, MARKETS  # The "flat" band, contracts per curve, and the market names

# Which time spreads to calculate: name -> curve position of the further contract.
# Each one is M1 (position 1) minus the contract at that position.
SPREAD_PAIRS = {
    "M1-M2": 2,     # Front month minus the next one: the most sensitive gauge of tightness right now
    "M1-M6": 6,     # Front month minus six months out: the slope over half a year
    "M1-M12": 12,   # Front month minus a year out: the slope across the whole curve
}


def label_structure(spread):
    """Name the shape of the curve that a time spread implies.

    spread -- a time spread in $/bbl (nearer contract minus further contract)
    Returns "flat" if it's within +/-NEUTRAL_BAND of zero, otherwise "backwardation" (positive)
    or "contango" (negative). The band stops the label flickering on days when the spread is near zero.
    """
    if abs(spread) <= NEUTRAL_BAND:                # Within $0.10 either side of zero (inclusive)...
        return "flat"                              # ...is too small to call a direction
    if spread > 0:                                 # Nearer contract dearer than the further one
        return "backwardation"                     # = oil now is worth more than oil later
    return "contango"                              # Otherwise nearer is cheaper = oil later is worth more


def time_spreads(curve):
    """Calculate M1-M2, M1-M6 and M1-M12 from one market's curve, each with its structure label.

    curve -- the Series returned by futures.curve_on(): prices indexed by delivery month, nearest first
    Returns a table with one row per spread: its name, the two contracts used, the value and the label.
    Exists so both markets go through exactly the same calculation.
    """
    if len(curve) < CURVE_MONTHS:                  # A short curve would make "M12" point at the wrong contract
        raise ValueError(f"Curve has only {len(curve)} contracts; {CURVE_MONTHS} are needed for M1-M12.")

    rows = []                                      # One dictionary per spread gets collected here
    for name, far_position in SPREAD_PAIRS.items():  # e.g. ("M1-M6", 6)
        near_price = curve.iloc[0]                 # M1: the first contract on the curve
        far_price = curve.iloc[far_position - 1]   # The further contract (positions count from 1, Python from 0)
        spread = round(near_price - far_price, 2)  # Nearer minus further, rounded to cents (prices are quoted in cents)
        rows.append({                              # Store this spread's details
            "spread": name,                        # e.g. "M1-M6"
            "contracts": f"{curve.index[0]} minus {curve.index[far_position - 1]}",  # The delivery months used, for checking
            "value": spread,                       # The spread in $/bbl
            "structure": label_structure(spread),  # backwardation / contango / flat
        })
    return pd.DataFrame(rows)                      # Turn the list into a table


def curve_spreads(curves):
    """Time spreads for every market, each tagged with the date its curve comes from.

    curves -- dictionary of market -> (curve, date), as built from futures.curve_on()
    Returns one table with columns market, date, spread, contracts, value and structure.
    Each curve uses its own latest complete date (one source per calculation), so Brent and WTI
    rows can carry different dates.
    """
    tables = []                                    # One table per market gets collected here
    for market, (curve, date) in curves.items():   # e.g. ("Brent", (curve, 2026-10-30))
        table = time_spreads(curve)                # That market's three spreads
        table.insert(0, "date", date)              # Add the curve's date as the second column...
        table.insert(0, "market", market)          # ...and the market name as the first
        tables.append(table)                       # Keep it
    return pd.concat(tables, ignore_index=True)    # Stack the markets into one table, numbered 0, 1, 2 ...


def brent_wti_spot(spot):
    """The Brent-WTI spot spread on the latest day EIA has published BOTH prices.

    spot -- the table from eia.fetch_spot(), with columns brent_spot and wti_spot
    Returns a dictionary: date, brent, wti and spread (Brent minus WTI, $/bbl).
    Both prices come from one source (EIA), but we still skip any day where only one is filled in.
    """
    both = spot[["brent_spot", "wti_spot"]].dropna()  # Keep only days where both prices exist
    date = both.index[-1]                          # The latest such day
    brent = both["brent_spot"].iloc[-1]            # Dated Brent on that day
    wti = both["wti_spot"].iloc[-1]                # WTI Cushing on that day
    return {                                       # Hand back everything needed to print and check it
        "date": date,                              # The day both prices are from
        "brent": brent,                            # Brent spot, $/bbl
        "wti": wti,                                # WTI spot, $/bbl
        "spread": round(brent - wti, 2),           # Brent minus WTI, rounded to cents
    }


def dated_brent_vs_future(spot, front_future):
    """Dated Brent (EIA spot) minus the Brent front-month future, on the latest date BOTH sources have.

    spot         -- the table from eia.fetch_spot() (we use its brent_spot column)
    front_future -- the Series from futures.front_month_continuous("Brent") (Yahoo's BZ=F)
    Returns a dictionary: date, dated_brent, front_future and spread ($/bbl).
    This combines two sources, so it follows the CLAUDE.md rule: EIA runs a few days behind Yahoo,
    so we use the latest day that appears in both, never each one's own latest day.
    """
    side_by_side = pd.concat([spot["brent_spot"], front_future], axis=1)  # Line the two series up by date, one column each
    both = side_by_side.dropna()                   # Keep only days where BOTH sources have a price
    date = both.index[-1]                          # The latest day common to both
    dated = both["brent_spot"].iloc[-1]            # Dated Brent on that day
    future = round(both[front_future.name].iloc[-1], 2)  # Front-month future on that day, rounded to cents
    return {                                       # Hand back everything needed to print and check it
        "date": date,                              # The shared day
        "dated_brent": dated,                      # Physical (spot) price, $/bbl
        "front_future": future,                    # Front-month futures price, $/bbl
        "spread": round(dated - future, 2),        # Spot minus future, rounded to cents
    }


def brent_wti_spot_history(spot):
    """The daily Brent-WTI spot spread from EIA, on every day both prices exist.

    spot -- the table from eia.fetch_spot()
    Returns a Series of Brent minus WTI ($/bbl) indexed by date.
    One source (EIA), so each day simply uses that day's two prices.
    """
    both = spot[["brent_spot", "wti_spot"]].dropna()   # Keep only days where both prices exist
    return (both["brent_spot"] - both["wti_spot"]).round(2)  # Brent minus WTI each day, rounded to cents


def fixed_contract_spread(prices, near, far, end, months=6):
    """The daily spread between two specific contracts, held fixed, over the `months` months up to `end`.

    prices    -- the table from futures.download_contracts()
    near, far -- the two contracts' delivery-month labels, e.g. "2026-12" and "2027-05"
    end       -- the last date to include (normally the curve's date)
    months    -- how many months of history to cover
    Returns a Series of near minus far ($/bbl), only on days both contracts have a price.
    Because the contracts never change, there are no jumps on roll days. But six months ago these
    two contracts sat further along the curve (e.g. M7 and M12), so this isn't a rolling M1-M6.
    """
    start = end - pd.DateOffset(months=months)     # The first date to include, e.g. six months before the curve date
    both = prices.loc[start:end, [near, far]].dropna()  # The two contracts' prices in that window, only days both traded
    return (both[near] - both[far]).round(2)       # Nearer minus further each day, rounded to cents


def wti_m1m2_history(history):
    """The daily WTI M1-M2 spread from EIA's futures history (2010 to April 2024).

    history -- the table from eia.fetch_wti_futures_history(), with columns wti_m1 and wti_m2
    Returns a Series of M1 minus M2 ($/bbl) indexed by date, skipping days missing a price.
    Shared by the percentile and the histogram, so both always use exactly the same numbers.
    """
    return (history["wti_m1"] - history["wti_m2"]).round(2).dropna()  # Daily M1-M2 in cents, skipping blank days


def wti_m1m2_percentile(today_spread, history):
    """Where today's WTI M1-M2 sits within EIA's daily WTI M1-M2 history (2010 to April 2024).

    today_spread -- today's WTI M1-M2 in $/bbl (from time_spreads())
    history      -- the table from eia.fetch_wti_futures_history(), with columns wti_m1 and wti_m2
    Returns a dictionary: the percentile, how many days it's based on, the history's date range,
    and its median, minimum and maximum (with dates) for context.
    Mixing today's Yahoo spread with the older EIA history is deliberate (see CLAUDE.md).
    """
    hist = wti_m1m2_history(history)               # Daily M1-M2 over 2010 to April 2024
    at_or_below = int((hist <= today_spread).sum())  # Count of historical days with a spread at or below today's
    percentile = at_or_below / len(hist) * 100     # Turn that count into a percentage of all days
    return {                                       # Hand back the result and its context
        "percentile": round(percentile, 1),        # e.g. 95.3 = steeper backwardation than on 95.3% of days
        "at_or_below": at_or_below,                # The count used, so the percentile can be checked by hand
        "days": len(hist),                         # Total days in the history
        "start": hist.index.min(),                 # First day of the history
        "end": hist.index.max(),                   # Last day (EIA stopped updating in April 2024)
        "median": round(hist.median(), 2),         # The typical M1-M2 over the period
        "min": hist.min(),                         # Deepest contango in the history
        "min_date": hist.idxmin(),                 # ...and the day it happened
        "max": hist.max(),                         # Steepest backwardation in the history
        "max_date": hist.idxmax(),                 # ...and the day it happened
    }


def summary_lines(curves, spot, brent_future, wti_history):
    """Run every calculation above and write the results as lines of text, with a date beside every number.

    curves       -- dictionary of market -> (curve, date) from futures.curve_on()
    spot         -- the table from eia.fetch_spot()
    brent_future -- the Series from futures.front_month_continuous("Brent")
    wti_history  -- the table from eia.fetch_wti_futures_history()
    Returns a list of strings, one per line. Exists so main.py (which saves them to a file) and the
    test block below (which prints them) share exactly the same summary.
    """
    lines = []                                     # The summary is built up here, one line at a time

    # 1 and 2. Time spreads and their labels
    lines.append("1. Time spreads (each curve on its own latest complete date)")  # Section heading
    table = curve_spreads(curves)                  # Both markets' spreads in one table
    for _, row in table.iterrows():                # One line per spread
        lines.append(f"   {row['market']:<6}{row['spread']:<8}on {row['date']:%d %b %Y}: "  # Market, spread name and date...
                     f"{row['value']:+7.2f}  {row['structure']:<14}({row['contracts']})")  # ...value with sign, label, contracts used

    # 3. Brent-WTI spot spread (one source: EIA)
    bw = brent_wti_spot(spot)                      # Latest day with both spot prices
    lines.append("")                               # Blank line between sections
    lines.append(f"2. Brent-WTI spot spread (EIA) on {bw['date']:%d %b %Y}")  # Heading with the date
    lines.append(f"   Brent {bw['brent']:.2f} - WTI {bw['wti']:.2f} = {bw['spread']:+.2f}")  # The working and the answer

    # 4. Dated Brent minus front-month future (two sources: latest shared date)
    db = dated_brent_vs_future(spot, brent_future) # Latest day both EIA and Yahoo have a price
    lines.append("")                               # Blank line between sections
    lines.append(f"3. Dated Brent minus front-month future, on {db['date']:%d %b %Y} (latest date both sources have)")  # Heading with the date
    lines.append(f"   Dated Brent {db['dated_brent']:.2f} - future {db['front_future']:.2f} = {db['spread']:+.2f}")  # The working and the answer

    # 5. Today's WTI M1-M2 against the 2010-2024 history
    is_wti_m1m2 = (table["market"] == "WTI") & (table["spread"] == "M1-M2")  # Find the WTI M1-M2 row
    wti_today = table.loc[is_wti_m1m2, "value"].iloc[0]  # Its value
    wti_date = curves["WTI"][1]                    # The date of the WTI curve it came from
    pct = wti_m1m2_percentile(wti_today, wti_history)  # Rank it against the history
    lines.append("")                               # Blank line between sections
    lines.append(f"4. WTI M1-M2 percentile vs EIA history "  # Heading...
                 f"({pct['start']:%d %b %Y} to {pct['end']:%d %b %Y}, {pct['days']:,} days)")  # ...with the history's date range
    lines.append(f"   Today's WTI M1-M2 ({wti_date:%d %b %Y}): {wti_today:+.2f}")  # Today's value with its date
    lines.append(f"   Percentile: {pct['percentile']:.1f}  ({pct['at_or_below']:,} of {pct['days']:,} days were at or below it)")  # The answer and the count behind it
    lines.append(f"   History median {pct['median']:+.2f}; "  # Context: the typical value...
                 f"min {pct['min']:+.2f} on {pct['min_date']:%d %b %Y}; "  # ...the deepest contango...
                 f"max {pct['max']:+.2f} on {pct['max_date']:%d %b %Y}")  # ...and the steepest backwardation
    return lines                                   # Hand back the finished summary


if __name__ == "__main__":                         # Only runs when you type "python spreads.py", not when imported
    from eia import fetch_spot, fetch_wti_futures_history  # EIA downloads (only this test block needs them)
    from futures import download_contracts, curve_on, front_month_continuous  # Yahoo downloads

    curves = {}                                    # market -> (curve, date) gets collected here
    for market in MARKETS:                         # "Brent" then "WTI"
        prices = download_contracts(market)        # Daily closes of every live contract
        curves[market] = curve_on(prices)          # The latest complete curve and its date
    spot = fetch_spot()                            # EIA Brent and WTI spot prices since 2010
    brent_future = front_month_continuous("Brent") # Yahoo's continuous Brent front-month series
    wti_history = fetch_wti_futures_history()      # EIA WTI contracts 1-4, 2010 to April 2024

    print()                                        # A blank line to separate the results from any download warnings
    print("\n".join(summary_lines(curves, spot, brent_future, wti_history)))  # Print the summary, one line per entry
