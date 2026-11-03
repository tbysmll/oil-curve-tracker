"""
test_curves.py - a quick check that futures.py can build today's Brent and WTI curves.

Run it with:  python test_curves.py
It downloads prices from Yahoo Finance and prints each curve with the date it comes from.
It does NOT call save_snapshot(), so running the test never adds rows to data/curve_snapshots.csv.
"""

from config import MARKETS, CURVE_MONTHS          # The markets to test ("Brent", "WTI") and how many contracts a curve should have
from futures import download_contracts, curve_on  # The two functions being tested


def show_curve(market):
    """Download one market's contracts, build its curve and print it as a table.

    market -- "Brent" or "WTI" (one of the keys in config.MARKETS)
    Returns nothing; it only prints. It exists so both markets go through exactly the same code.
    """
    prices = download_contracts(market)           # Table of daily closes: one row per date, one column per delivery month
    curve, date = curve_on(prices)                # The latest complete curve, plus the trading day it actually comes from

    print(f"\n{market} futures curve - prices from {date:%a %d %b %Y}")  # Heading, with the date next to the numbers (CLAUDE.md rule)
    print(f"{'Pos':<5}{'Delivery':<10}{'Price $/bbl':>12}")              # Column headers: curve position, delivery month, price
    for position, (contract, price) in enumerate(curve.items(), start=1):  # Walk along the curve; position 1 is the front month
        print(f"M{position:<4}{contract:<10}{price:>12.2f}")             # One line per contract, e.g. "M1   2027-01      65.20"

    if len(curve) == CURVE_MONTHS:                # Did we get the full 12 contracts?
        print(f"OK: {len(curve)} contracts")      # Yes: say so
    else:                                         # No: some back months had no recent price
        print(f"WARNING: only {len(curve)} of {CURVE_MONTHS} contracts")  # Flag it so it isn't missed


if __name__ == "__main__":                        # Only run this when the file is run directly, not when it's imported
    for market in MARKETS:                        # "Brent" then "WTI", straight from config.py
        show_curve(market)                        # Print that market's curve
