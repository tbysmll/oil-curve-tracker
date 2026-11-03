"""
eia.py - downloads official daily oil prices from the EIA API.

Two things come from EIA:
  1. Spot prices for Brent and WTI (physical crude for prompt delivery), still updated daily.
  2. WTI futures contracts 1-4. EIA stopped updating these in April 2024, so we only use
     them as long-run history to judge whether today's spreads are normal or extreme.
"""

import pandas as pd                        # pandas holds the data as a table (a "DataFrame")
import requests                            # requests sends the web request to EIA and gets the reply
from config import EIA_API_KEY, EIA_BASE_URL, LONG_RUN_START  # settings from config.py

# EIA's series codes, mapped to the clearer column names we use in our tables
SPOT_SERIES = {
    "RBRTE": "brent_spot",   # Europe Brent spot price FOB (Dated Brent), $/bbl
    "RWTC": "wti_spot",      # WTI spot price at Cushing, Oklahoma, $/bbl
}
FUTURES_SERIES = {
    "RCLC1": "wti_m1",       # WTI futures contract 1 (front month)
    "RCLC2": "wti_m2",       # WTI futures contract 2 (second month)
    "RCLC3": "wti_m3",       # contract 3
    "RCLC4": "wti_m4",       # contract 4
}

PAGE_SIZE = 5000             # EIA returns at most 5,000 rows per request, so longer histories come in pages


def fetch_series(route, series_map, start=None):
    """Download daily EIA series and return a table with one row per date and one column per series.

    route      -- which part of EIA's data tree to ask, e.g. "petroleum/pri/spt" for spot prices
    series_map -- dictionary of EIA series codes -> our column names (e.g. SPOT_SERIES above)
    start      -- optional first date to download, as "YYYY-MM-DD"
    """
    if not EIA_API_KEY:                                        # Stop early with a clear message if there's no key
        raise RuntimeError("No EIA_API_KEY found. Put it in a .env file (see .env.example).")

    rows = []                                                  # Every row EIA sends back gets collected in this list
    offset = 0                                                 # Which row to start from; moves forward one page at a time

    while True:                                                # Keep asking for pages until EIA has nothing left
        params = {                                             # The options sent to EIA with each request
            "api_key": EIA_API_KEY,                            # Proves who we are
            "frequency": "daily",                              # Daily prices, not weekly or monthly averages
            "data[0]": "value",                                # We want the price itself
            "facets[series][]": list(series_map),              # Which series to return (requests repeats this key for each code)
            "sort[0][column]": "period",                       # Sort by date...
            "sort[0][direction]": "asc",                       # ...oldest first
            "offset": offset,                                  # Skip the rows we've already received
            "length": PAGE_SIZE,                               # Ask for a full page
        }
        if start:                                              # Only add a start date if one was given
            params["start"] = start

        url = f"{EIA_BASE_URL}/{route}/data/"                  # Full address, e.g. https://api.eia.gov/v2/petroleum/pri/spt/data/
        reply = requests.get(url, params=params, timeout=60)   # Send the request; give up after 60 seconds
        reply.raise_for_status()                               # If EIA returned an error (bad key, outage), stop here with that error
        page = reply.json()["response"]["data"]                # Turn the reply into Python data and pull out the list of rows
        rows.extend(page)                                      # Add this page's rows to the collection

        if len(page) < PAGE_SIZE:                              # A short page means it was the last one
            break                                              # So leave the loop
        offset += PAGE_SIZE                                    # Otherwise move on to the next page

    table = pd.DataFrame(rows)                                 # Turn the list of rows into a table
    table["value"] = pd.to_numeric(table["value"], errors="coerce")  # Prices arrive as text; convert to numbers (blanks become NaN)
    table["period"] = pd.to_datetime(table["period"])          # Dates arrive as text; convert to real dates

    wide = table.pivot_table(index="period", columns="series", values="value")  # Reshape: one row per date, one column per series
    wide = wide.rename(columns=series_map)                     # Swap EIA's codes for our readable names
    wide.index.name = "date"                                   # Name the date column
    wide.columns.name = None                                   # Remove the leftover "series" label from the column header
    return wide                                                # Hand the finished table back


def fetch_spot(start=LONG_RUN_START):
    """Brent and WTI spot prices from `start` to the latest day EIA has published."""
    return fetch_series("petroleum/pri/spt", SPOT_SERIES, start)   # Spot prices live under petroleum -> prices -> spot


def fetch_wti_futures_history(start=LONG_RUN_START):
    """WTI contracts 1-4 from `start` until EIA stopped updating them (April 2024)."""
    return fetch_series("petroleum/pri/fut", FUTURES_SERIES, start)  # Futures live under petroleum -> prices -> futures
