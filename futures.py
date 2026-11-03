"""
futures.py - builds today's Brent and WTI futures curves from Yahoo Finance.

A futures "curve" is the price of each delivery month lined up in order:
M1 is the front month (the next contract to expire), M2 the one after, and so on.

Yahoo removes a contract once it expires, so we can't rebuild a perfect rolling M1-M2
history for past dates. Instead, every time the tracker runs it saves that day's curve
to data/curve_snapshots.csv, so a true history builds up from the day you start running it.
"""

import datetime as dt                 # dt handles dates (today's date, building delivery months)
from zoneinfo import ZoneInfo        # Time zones, so "before 22:00" means UK time even on GitHub's servers
import pandas as pd                   # pandas tables
import yfinance as yf                 # yfinance downloads prices from Yahoo Finance
from config import MONTH_CODES, MARKETS, CURVE_MONTHS, HISTORY_START, DATA_DIR  # settings
from config import SETTLEMENT_HOUR_UK, FRONT_MONTH_START  # When today's prices count as settled; front-month history start

SNAPSHOT_FILE = DATA_DIR / "curve_snapshots.csv"   # Where each day's curve is saved
UK_TIME = ZoneInfo("Europe/London")               # The UK time zone (GMT in winter, BST in summer)


def settled_only(table, now=None):
    """Keep only settled prices: drop any row that is still live trading.

    table -- a table or Series of daily prices from Yahoo, indexed by date
    now   -- the time to judge by (defaults to the current UK time); a different time can be passed in to test it
    Returns the same data without unsettled rows: anything dated after today, and today's row if it's still
    before SETTLEMENT_HOUR_UK. During trading hours Yahoo's latest row is live prices, not the day's settlement,
    so a daytime run uses the previous trading day's settlement instead. Applied to every Yahoo download, so
    curve_on(), the front-month series, the charts, the tiles and the snapshot all only ever see settlements.
    """
    now = now or dt.datetime.now(UK_TIME)            # The current UK time, unless a time was given
    today = pd.Timestamp(now.date())                 # Today's date, in the same form as the table's dates
    if now.hour >= SETTLEMENT_HOUR_UK:               # After 22:00 UK, today's prices have settled...
        cutoff = today + pd.Timedelta(days=1)        # ...so keep everything up to and including today
    else:                                            # Before 22:00 UK, today's row is still live...
        cutoff = today                               # ...so keep only rows from before today
    return table[table.index < cutoff]               # Drop the unsettled rows


def contract_tickers(market, today=None):
    """List the Yahoo tickers for the coming delivery months, e.g. BZF27.NYM for Brent Jan 2027.

    Returns a list of (ticker, delivery month) pairs, starting from the current month.
    We list a few more months than we need because the nearest one or two will already
    have expired (Brent stops trading about two months before its delivery month).
    """
    today = today or dt.date.today()                 # Use today's date unless a different date was passed in
    root = MARKETS[market]["root"]                   # "BZ" for Brent, "CL" for WTI
    exchange = MARKETS[market]["exchange"]           # "NYM" (NYMEX) for both
    pairs = []                                       # The (ticker, month) pairs get collected here

    for i in range(CURVE_MONTHS + 4):                # 12 months we want + 4 spare to cover expired ones
        months_from_jan = today.month - 1 + i        # Count of months since January this year (0 = Jan)
        year = today.year + months_from_jan // 12    # Whole years to add when we pass December
        month = months_from_jan % 12 + 1             # The calendar month, 1-12
        code = MONTH_CODES[month - 1]                # Its letter code, e.g. 1 -> "F"
        ticker = f"{root}{code}{str(year)[-2:]}.{exchange}"  # Build the ticker, e.g. "BZ" + "F" + "27" + ".NYM"
        pairs.append((ticker, f"{year}-{month:02d}"))       # Store it with a readable label like "2027-01"

    return pairs                                     # Hand back the full list


def download_contracts(market):
    """Download the daily closing price of every contract in contract_tickers().

    Returns a table: one row per date, one column per delivery month (e.g. "2027-01"),
    with only the contracts Yahoo actually has data for.
    """
    pairs = contract_tickers(market)                 # The tickers we want to ask Yahoo for
    tickers = [t for t, _ in pairs]                  # Just the ticker strings
    labels = dict(pairs)                             # Lookup from ticker to its readable month label

    raw = yf.download(                               # One request for all tickers at once
        tickers,                                     # The list of contracts
        start=HISTORY_START,                         # From this date onwards
        auto_adjust=False,                           # Raw prices (adjustments are for stock dividends, not futures)
        progress=False,                              # Don't print a progress bar
        threads=False,                               # Download one contract at a time: parallel downloads can clash over
                                                     # yfinance's cache file ("database is locked") and silently lose a contract
    )["Close"]                                       # Keep only the closing price of each day

    raw = raw.dropna(axis=1, how="all")              # Drop contracts Yahoo returned no data for (already expired)
    if raw.shape[1] < CURVE_MONTHS:                  # Fewer than 12 contracts with prices means the download failed
        raise RuntimeError(                          # Stop with a clear message instead of a confusing error later
            f"Yahoo returned prices for only {raw.shape[1]} {market} contracts "  # Say how many came back...
            f"(at least {CURVE_MONTHS} needed). The download failed or was blocked; nothing has been saved."  # ...and what it means
        )                                            # End of the error message
    raw = raw.rename(columns=labels)                 # Swap tickers for month labels, e.g. BZF27.NYM -> 2027-01
    raw = raw[sorted(raw.columns)]                   # Order columns by delivery month, nearest first
    raw.index = pd.to_datetime(raw.index).tz_localize(None)  # Plain dates without a time zone, so they line up with EIA dates
    raw = settled_only(raw)                          # Settlement prices only: drop today's live row before 22:00 UK
    raw.index.name = "date"                          # Name the date column
    raw.columns.name = None                          # Tidy up the column header
    return raw                                       # Hand back the table


def check_consecutive(curve):
    """Stop with an error if the curve skips a delivery month.

    curve -- a Series indexed by delivery month labels like "2027-01", nearest first
    Returns nothing if the months run on one after another (Dec 26, Jan 27, Feb 27 ...).
    Exists because a failed download or a blank back month would otherwise be skipped silently,
    shifting every later contract up a place, so "M2" would really be M3 and every spread would be wrong.
    It can't catch a missing FIRST contract, which looks just like one that has expired.
    """
    gaps = []                                        # Any missing stretches get collected here
    for i in range(1, len(curve)):                   # Compare each contract with the one before it
        earlier = curve.index[i - 1]                 # e.g. "2026-12"
        later = curve.index[i]                       # e.g. "2027-01"
        earlier_count = int(earlier[:4]) * 12 + int(earlier[5:])  # Turn "YYYY-MM" into a running month count
        later_count = int(later[:4]) * 12 + int(later[5:])        # Same for the later contract
        if later_count - earlier_count != 1:         # Neighbouring contracts should be exactly one month apart
            gaps.append(f"{earlier} -> {later}")     # Note where the gap is
    if gaps:                                         # If any gap was found...
        raise ValueError(f"Curve skips delivery months: {', '.join(gaps)}. "  # ...stop and say exactly where
                         "A contract failed to download or had no recent price; try again later.")


def curve_on(prices, date=None):
    """The curve on a given date: the first CURVE_MONTHS contracts that have a price that day.

    prices -- the table from download_contracts()
    date   -- which day to read; defaults to the latest day in the table
    Returns a Series indexed by delivery month, nearest first, and the actual date used.
    """
    if date is None:                                 # No date given, so find the most recent COMPLETE day.
        # During trading hours Yahoo's latest row is live prices, and thin back months may not have
        # traded yet. Mixing live prices with old ones bends the curve, so we step back day by day
        # until every one of the first 12 contracts has a price on the same day.
        for candidate in prices.index[::-1][:5]:     # The 5 most recent days, newest first
            row = prices.loc[candidate]              # Prices on that day
            front = row.dropna().index.min()         # Nearest contract that traded that day
            live = row[prices.columns >= front]      # That contract and every later one
            if live.iloc[:CURVE_MONTHS].notna().all():  # Do the first 12 all have a price?
                date = candidate                     # Yes: use this day
                break                                # and stop looking
        else:                                        # (runs only if no complete day was found in the loop)
            date = prices.index.max()                # Fall back to the latest day; the gap-filling below handles blanks
    else:
        date = prices.index[prices.index <= pd.Timestamp(date)].max()  # Otherwise the last trading day on or before it

    today_row = prices.loc[date]                     # That day's prices (blank for contracts that didn't trade)
    front = today_row.dropna().index.min()           # The nearest contract that DID trade that day is the front month (M1);
                                                     # anything nearer than it has expired
    live = prices.loc[:date, prices.columns >= front]  # Keep only the front month and later contracts, up to that date
    # Back-month contracts are thinly traded and sometimes have no price on a given day.
    # Fill each gap with that contract's most recent price, but only if it's at most 3 trading days old.
    filled = live.ffill(limit=3).loc[date]           # ffill = "forward fill": copy the last known price forward
    curve = filled.dropna().sort_index().iloc[:CURVE_MONTHS]  # Drop any still-blank contracts, nearest first, keep 12
    check_consecutive(curve)                         # Stop if dropping a blank contract left a gap in the months
    return curve, date                               # Return both the curve and the date it's from


def save_snapshot(market, date, curve):
    """Append today's curve to data/curve_snapshots.csv so a daily history builds up over time."""
    new = pd.DataFrame({                             # One row per contract on the curve
        "date": date.strftime("%Y-%m-%d"),           # The trading day the prices are from
        "market": market,                            # "Brent" or "WTI"
        "position": range(1, len(curve) + 1),        # 1 = M1 (front month), 2 = M2, ...
        "contract": curve.index,                     # The delivery month, e.g. "2027-01"
        "price": curve.values.round(2),              # The price, rounded to cents
    })

    if SNAPSHOT_FILE.exists():                       # If we've saved snapshots before...
        old = pd.read_csv(SNAPSHOT_FILE)             # ...load them
        both = pd.concat([old, new])                 # Stack the old and new rows together
    else:
        both = new                                   # First run: there's nothing to add to

    # If the tracker runs twice on the same day, keep only the latest numbers for that day
    both = both.drop_duplicates(subset=["date", "market", "position"], keep="last")
    both = both.sort_values(["market", "date", "position"])   # Neat order: by market, then date, then curve position
    both.to_csv(SNAPSHOT_FILE, index=False)          # Write it back to disk


def load_snapshots():
    """Read every saved curve snapshot (an empty table if none have been saved yet)."""
    if not SNAPSHOT_FILE.exists():                   # Nothing saved yet
        return pd.DataFrame(columns=["date", "market", "position", "contract", "price"])  # Empty table with the right columns
    snaps = pd.read_csv(SNAPSHOT_FILE, parse_dates=["date"])  # Load, reading the date column as real dates
    return snaps                                     # Hand it back


def front_month_continuous(market):
    """Yahoo's continuous front-month series (BZ=F or CL=F): always the nearest contract.

    Used to compare Dated Brent (physical spot) with the front-month future, and for Figure 5.
    Starts at FRONT_MONTH_START (earlier than the contracts) so a two-year average is possible.
    """
    ticker = f"{MARKETS[market]['root']}=F"          # e.g. "BZ=F" for Brent
    raw = yf.download(ticker, start=FRONT_MONTH_START, auto_adjust=False, progress=False)["Close"]  # Daily closes
    series = raw.squeeze("columns").dropna()         # yfinance returns a one-column table; turn it into a simple Series, minus blanks
    series.index = pd.to_datetime(series.index).tz_localize(None)  # Plain dates, no time zone
    series = settled_only(series)                    # Settlement prices only: drop today's live row before 22:00 UK
    if series.empty:                                 # No prices at all means the download failed
        raise RuntimeError(f"Yahoo returned no prices for {ticker}. The download failed or was blocked.")  # Stop clearly
    series.name = f"{market.lower()}_front_future"   # e.g. "brent_front_future"
    return series                                    # Hand it back
