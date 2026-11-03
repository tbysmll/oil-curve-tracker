"""
report.py - turns the tracker's results into things people read.

  summary_rows()      - today's numbers as table rows, each with its data date (built once, used everywhere)
  headline_tiles()    - the six headline numbers shown as tiles across the top of the dashboard
  summary_markdown()  - the rows plus the charts (with their titles and sources) as Markdown, for README.md
                        and output/summary.md
  write_html()        - docs/index.html, the dashboard that GitHub Pages publishes

The dashboard also shows Toby's own commentary, read from commentary.txt (edited by hand).
It's one self-contained HTML file with its styling built in and no JavaScript, so it loads fast anywhere.
"""

import html                                        # html.escape makes text safe to place inside a web page
import pandas as pd                                # pandas, for turning contract labels into dates
from config import BASE_DIR, DOCS_DIR, REPO_URL    # Folders, and the GitHub link for the page footer
import chart_style as style                        # The house palette and date format, so the page matches the charts
from interactive import PLOTLY_SCRIPT              # The <script> line that loads Plotly's JavaScript for the interactive charts
from spreads import (                              # The calculations
    curve_spreads,                                 # Both markets' time spreads, each with its date
    time_spreads,                                  # One curve's M1-M2, M1-M6, M1-M12
    brent_wti_spot,                                # Brent-WTI spot spread on EIA's latest shared day
    brent_wti_spot_history,                        # The daily Brent-WTI spot spread
    dated_brent_vs_future,                         # Dated Brent minus the front-month future
    wti_m1m2_percentile,                           # Where today's WTI M1-M2 sits in history
)

COMMENTARY_FILE = BASE_DIR / "commentary.txt"      # Toby's hand-written commentary
REPORT_FILE = DOCS_DIR / "index.html"              # The web page; "index.html" is the file a website shows by default

NOTES = [                                          # Caveats shown with the numbers in every report
    "Brent and WTI curves can come from different days: each uses its latest day with all 12 contracts priced.",  # curve_on() behaviour
    "If the tracker ran during US trading hours, the latest futures prices are live rather than closing prices.",  # Yahoo live prices
    "EIA spot prices run a few days behind; the WTI percentile deliberately compares today with 2010-2024.",  # EIA lag and the agreed exception
]                                                  # End of the notes

# The page's styling (CSS), matching the charts' research-dashboard look.
# PALETTE turns chart_style's colours into CSS "variables" (e.g. --navy), so the page and the charts share
# one palette: change a colour in chart_style.py and both follow. {{ and }} are how an f-string writes { and }.
PALETTE = (f":root {{ --navy: {style.NAVY}; --mid-blue: {style.MID_BLUE}; --gold: {style.GOLD}; "  # The five house colours...
           f"--dark-grey: {style.DARK_GREY}; --light-grey: {style.LIGHT_GREY}; --white: {style.WHITE}; }}")  # ...plus white

# Each line below sets how one kind of element looks; var(--navy) means "the navy from the palette above"
STYLE = PALETTE + """
* { box-sizing: border-box; }                                          /* Widths include padding, which keeps the grid maths simple */
body { margin: 0; font-family: Arial, Helvetica, "Liberation Sans", sans-serif; color: var(--dark-grey); background: var(--white); line-height: 1.45; font-size: 14px; } /* Same font and text colour as the charts */
.wrap { max-width: 1280px; margin: 0 auto; padding: 0 24px; }          /* One centred page width, used by every band */
.masthead { background: var(--navy); border-bottom: 3px solid var(--gold); }  /* Navy band across the top, with a gold rule under it */
.masthead .wrap { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; padding-top: 18px; padding-bottom: 16px; }  /* Title on the left, timestamp on the right */
.label { margin: 0; color: var(--gold); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }  /* Small gold label above the title */
h1 { margin: 2px 0; font-size: 26px; color: var(--white); }            /* Page title, white on navy */
.masthead .subtitle { margin: 0; color: var(--light-grey); font-size: 13px; }  /* Subtitle, light grey on navy */
.stamp { color: var(--light-grey); font-size: 12px; text-align: right; white-space: nowrap; }  /* "Updated ..." on the right of the band */
.stamp strong { display: block; color: var(--white); font-size: 15px; }  /* The date and time itself, larger and white */
.tiles { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin: 20px 0; }  /* Six headline tiles in a row */
.tile { border: 1px solid var(--light-grey); border-top: 3px solid var(--navy); padding: 10px 12px; }  /* Each tile: hairline frame, navy top edge */
.tile-label { margin: 0; font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }  /* What the tile shows */
.tile-value { margin: 4px 0 0; font-size: 26px; font-weight: 700; color: var(--navy); font-variant-numeric: tabular-nums; }  /* The headline number */
.tile-unit { font-size: 12px; font-weight: 400; color: var(--dark-grey); margin-left: 3px; }  /* "$/bbl" after the number, small */
.tile-detail { margin: 2px 0 0; font-size: 12px; font-weight: 700; }   /* The change or reading, e.g. "▲ +0.98 vs 30 Oct" */
.tile-date { margin: 2px 0 0; font-size: 11px; }                       /* The data date, smallest */
.tile-info { margin: 8px 0 0; padding-top: 7px; border-top: 1px solid var(--light-grey); font-size: 11.5px; line-height: 1.4; }  /* The plain-English explanation, under a hairline */
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 20px; align-items: start; }  /* Charts on the left, sidebar on the right */
.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }  /* Charts in two columns */
.card { border: 1px solid var(--light-grey); padding: 14px 16px 12px; background: var(--white); }  /* Every chart and panel sits in a card */
.card.wide { grid-column: 1 / -1; }                                    /* Figure 1 spans both columns */
.fig { margin: 0; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mid-blue); }  /* "FIGURE 1" */
.card h3 { margin: 3px 0 2px; font-size: 15px; line-height: 1.3; color: var(--navy); }  /* The takeaway title */
.sub { margin: 0 0 8px; font-size: 12px; }                             /* What's plotted and the units */
.card img { display: block; width: 100%; height: auto; }               /* The chart fills its card */
.card > a { display: block; cursor: zoom-in; }                         /* A static chart is clickable, with a magnifier cursor */
.plot { width: 100%; }                                                 /* Interactive charts fill their card */
.hint { font-style: italic; }                                          /* "Hover for exact values..." in italics */
.foot { margin: 6px 0 0; font-size: 11px; }                            /* Note and source lines under the chart */
.side h2, .numbers h2 { margin: 0 0 8px; font-size: 15px; color: var(--navy); padding-bottom: 6px; border-bottom: 2px solid var(--navy); }  /* Panel headings */
.side .card + .card { margin-top: 20px; }                              /* Space between the sidebar's cards */
.side p { margin: 0 0 10px; }                                          /* Space between paragraphs */
.side ul { margin: 0; padding-left: 18px; font-size: 12px; }           /* The method notes list */
.side li { margin-bottom: 6px; }                                       /* Space between notes */
.dated { font-weight: 700; color: var(--navy); }                       /* The date line at the top of the commentary */
.numbers { margin-top: 20px; }                                         /* Space above the full numbers table */
.table-wrap { overflow-x: auto; }                                      /* On a phone the table scrolls sideways instead of squashing */
table { width: 100%; border-collapse: collapse; font-size: 13px; }     /* Full-width table with single-line borders */
th, td { padding: 6px 10px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--light-grey); }  /* Cell spacing and light grey row lines */
th { background: var(--navy); color: var(--white); font-weight: 700; } /* Navy header row with white text */
td:first-child { min-width: 8em; }                                     /* Wide enough that "Brent M1-M12" never breaks at its hyphen */
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }  /* Numbers right-aligned so the decimals line up */
footer { margin: 28px auto 40px; font-size: 12px; }                    /* Small footer */
a { color: var(--mid-blue); }                                          /* Links in the mid blue */
@media (max-width: 1100px) { .tiles { grid-template-columns: repeat(3, 1fr); } .layout { grid-template-columns: 1fr; } }  /* Tablet: 3 tiles a row, sidebar moves below */
@media (max-width: 700px) { .tiles { grid-template-columns: repeat(2, 1fr); } .charts { grid-template-columns: 1fr; } .masthead .wrap { display: block; } .stamp { text-align: left; margin-top: 8px; } }  /* Phone: one column */
"""


def summary_rows(curves, spot, brent_future, wti_history):
    """Today's numbers as table rows, each with the date its prices come from.

    curves       -- dictionary of market -> (curve, date) from futures.curve_on()
    spot         -- the table from eia.fetch_spot()
    brent_future -- the Series from futures.front_month_continuous("Brent")
    wti_history  -- the table from eia.fetch_wti_futures_history()
    Returns a list of dictionaries with the keys measure, value, reading, date and working, all as text.
    Built once and shared by the README, output/summary.md and the web page, so they can never disagree.
    """
    table = curve_spreads(curves)                  # Both markets' M1-M2, M1-M6, M1-M12, each with its curve's date
    bw = brent_wti_spot(spot)                      # Brent-WTI spot spread on EIA's latest day with both prices
    db = dated_brent_vs_future(spot, brent_future) # Dated Brent minus the front-month future, on the latest shared date
    is_wti_m1m2 = (table["market"] == "WTI") & (table["spread"] == "M1-M2")  # Find the WTI M1-M2 row
    wti_today = table.loc[is_wti_m1m2, "value"].iloc[0]  # Its value
    wti_date = curves["WTI"][1]                    # The date of the WTI curve it came from
    pct = wti_m1m2_percentile(wti_today, wti_history)  # Where it sits in the 2010-2024 EIA history

    rows = []                                      # The finished rows get collected here
    for _, row in table.iterrows():                # One row per time spread
        rows.append({                              # e.g. Brent M1-M2 | +3.07 | backwardation | 02 Nov 2026 | 2027-01 minus 2027-02
            "measure": f"{row['market']} {row['spread']}",  # Which spread
            "value": f"{row['value']:+.2f}",       # Its value with a + or - sign
            "reading": row["structure"],           # backwardation / contango / flat
            "date": f"{row['date']:%d %b %Y}",     # The curve's date
            "working": row["contracts"],           # The two contracts subtracted
        })
    rows.append({                                  # Brent-WTI spot spread (one source: EIA)
        "measure": "Brent-WTI spot spread (EIA)",  # Which number
        "value": f"{bw['spread']:+.2f}",           # Its value
        "reading": "location spread",              # A location spread, not a time spread, so no backwardation label
        "date": f"{bw['date']:%d %b %Y}",          # EIA's latest day with both prices
        "working": f"Brent {bw['brent']:.2f} minus WTI {bw['wti']:.2f}",  # The subtraction
    })
    rows.append({                                  # Dated Brent minus the front-month future (two sources)
        "measure": "Dated Brent minus front-month future",  # Which number
        "value": f"{db['spread']:+.2f}",           # Its value
        "reading": "spot above future" if db["spread"] > 0 else "spot below future",  # Plain-English reading of the sign
        "date": f"{db['date']:%d %b %Y} (latest date both sources have)",  # The shared date (CLAUDE.md rule)
        "working": f"EIA {db['dated_brent']:.2f} minus Yahoo BZ=F {db['front_future']:.2f}",  # The subtraction
    })
    rows.append({                                  # Today's WTI M1-M2 against the EIA history
        "measure": "WTI M1-M2 percentile vs EIA history",  # Which number
        "value": f"{pct['percentile']:.1f}",       # The percentile
        "reading": "percentile (not $/bbl)",       # Flag that this one isn't a price
        "date": f"today {wti_date:%d %b %Y}; history {pct['start']:%d %b %Y} to {pct['end']:%d %b %Y}",  # Both dates involved
        "working": f"{pct['at_or_below']:,} of {pct['days']:,} days at or below {wti_today:+.2f}",  # The count behind it
    })
    return rows                                    # Hand back the finished rows


def change_text(change, since):
    """Describe a day-on-day change for a tile, e.g. "▲ +0.98 vs 30 Oct".

    change -- the change in $/bbl
    since  -- the earlier date it's measured from
    Returns the text. The arrow shows the direction at a glance; the number and date show exactly what moved.
    """
    if change > 0:                                 # Went up...
        arrow = "▲"                                # ...arrow up
    elif change < 0:                               # Went down...
        arrow = "▼"                                # ...arrow down
    else:                                          # Exactly unchanged...
        arrow = "–"                                # ...a dash
    return f"{arrow} {change:+.2f} vs {since:%d %b}"  # e.g. "▲ +0.98 vs 30 Oct"


def slope_meaning(curve, m1m12):
    """Explain a market's M1-M12 spread in one sentence for its tile.

    curve -- the market's curve from futures.curve_on() (for the two contract months)
    m1m12 -- that curve's M1-M12 row from time_spreads(), with "value" and "structure"
    Returns the sentence, which changes with the data (backwardation, contango or flat).
    """
    near = pd.Timestamp(curve.index[0]).strftime(style.DATE_FORMAT)   # The front month, e.g. "Jan-27"
    far = pd.Timestamp(curve.index[11]).strftime(style.DATE_FORMAT)   # The 12th month, e.g. "Dec-27"
    value = abs(m1m12["value"])                    # The size of the gap, without its sign
    if m1m12["structure"] == "backwardation":      # Nearer contract dearer...
        return (f"Oil for {near} delivery costs {value:.2f} $/bbl more than for {far}. That's backwardation: "  # ...say so...
                "buyers pay up for oil now, a sign of tight supply today.")  # ...and what it signals
    if m1m12["structure"] == "contango":           # Nearer contract cheaper...
        return (f"Oil for {near} delivery costs {value:.2f} $/bbl less than for {far}. That's contango: "  # ...say so...
                "plenty of oil now, so later barrels cost more (storage and financing).")  # ...and what it signals
    return (f"{near} and {far} are within $0.10 of each other: a flat curve, "  # Within the neutral band...
            "with no real premium for oil now over oil in a year.")  # ...so no clear signal


def percentile_meaning(percentile):
    """Explain the WTI M1-M2 percentile in one sentence for its tile.

    percentile -- today's percentile against 2010-2024 (0-100)
    Returns the sentence, which changes with the data.
    """
    if percentile >= 90:                           # Near the top of its history...
        reading = "historically tight: oil for this month is in unusually high demand"  # ...very strong backwardation
    elif percentile <= 10:                         # Near the bottom...
        reading = "historically loose: unusually deep contango, with plenty of oil now"  # ...very weak front end
    else:                                          # Anywhere in between...
        reading = "within its normal range"        # ...nothing unusual
    return (f"WTI front month minus the next month. Today's spread is at or above {percentile:.0f}% of "  # What it is...
            f"days from 2010 to 2024: {reading}.")  # ...and how unusual today is


def physical_meaning(spread):
    """Explain Dated Brent minus the front-month future in one sentence for its tile.

    spread -- Dated Brent minus the front-month Brent future, $/bbl
    Returns the sentence, which changes with the sign of the spread.
    """
    if spread > 0:                                 # Physical dearer than futures...
        sign = "Positive: buyers are paying a premium to get physical barrels quickly."  # ...prompt oil is scarce
    else:                                          # Physical cheaper (or equal)...
        sign = "Negative: prompt physical barrels are cheaper than futures, so prompt oil isn't scarce."  # ...no scramble for barrels
    return f"Physical Brent cargoes minus the nearest Brent future, on the latest date both have. {sign}"  # What it is, then the reading


def headline_tiles(curves, prices, spot, brent_future, wti_history):
    """The six headline numbers shown as tiles across the top of the dashboard.

    curves       -- dictionary of market -> (curve, date) from futures.curve_on()
    prices       -- dictionary of market -> price table from futures.download_contracts()
    spot         -- the table from eia.fetch_spot()
    brent_future -- the Series from futures.front_month_continuous("Brent")
    wti_history  -- the table from eia.fetch_wti_futures_history()
    Returns a list of dictionaries with the keys label, value, unit, detail, date and info (a plain-English
    explanation), all as text. Day-on-day changes for M1 compare the SAME contract on its previous trading day, so a contract
    roll can never show up as a price move.
    """
    tiles = []                                     # The finished tiles get collected here
    for market, (curve, date) in curves.items():   # Tiles 1 and 2: each market's front month
        contract = curve.index[0]                  # Today's M1 contract, e.g. "2027-01"
        history = prices[market][contract].loc[:date].dropna()  # That contract's daily closes up to the curve date
        latest, previous = history.iloc[-1], history.iloc[-2]  # Its price on the curve date and on the trading day before
        tiles.append({                             # e.g. BRENT M1 · JAN-27 | 104.77 $/bbl | ▼ -8.66 vs 30 Oct | 02 Nov 2026
            "label": f"{market} M1 · {pd.Timestamp(contract).strftime(style.DATE_FORMAT)}",  # Which contract
            "value": f"{latest:.2f}",              # The price
            "unit": "$/bbl",                       # Its unit
            "detail": change_text(latest - previous, history.index[-2]),  # The day-on-day change, same contract
            "date": f"{date:%d %b %Y}",            # The data date
            "info": (f"Price of the nearest {market} futures contract, for delivery in "  # What the number is...
                     f"{pd.Timestamp(contract):%B %Y}. The change compares the same contract with its previous close."),  # ...and how the change is measured
        })

    brent_curve, brent_date = curves["Brent"]      # Tile 3: Brent's curve slope
    brent_m1m12 = time_spreads(brent_curve).set_index("spread").loc["M1-M12"]  # Its M1-M12 row
    tiles.append({                                 # e.g. BRENT M1-M12 | +19.79 $/bbl | backwardation | 02 Nov 2026
        "label": "Brent M1-M12",                   # Which spread
        "value": f"{brent_m1m12['value']:+.2f}",   # Its value
        "unit": "$/bbl",                           # Its unit
        "detail": brent_m1m12["structure"],        # backwardation / contango / flat
        "date": f"{brent_date:%d %b %Y}",          # The data date
        "info": slope_meaning(brent_curve, brent_m1m12),  # What the slope means today, in words
    })

    wti_curve, wti_date = curves["WTI"]            # Tile 4: WTI's front spread against history
    wti_m1m2 = time_spreads(wti_curve).set_index("spread").loc["M1-M2", "value"]  # Today's WTI M1-M2
    pct = wti_m1m2_percentile(wti_m1m2, wti_history)  # Its percentile in 2010-2024
    tiles.append({                                 # e.g. WTI M1-M2 | +1.52 $/bbl | percentile 96.6 vs 2010-24 | 03 Nov 2026
        "label": "WTI M1-M2",                      # Which spread
        "value": f"{wti_m1m2:+.2f}",               # Its value
        "unit": "$/bbl",                           # Its unit
        "detail": f"percentile {pct['percentile']:.1f} vs 2010-24",  # How unusual it is
        "date": f"{wti_date:%d %b %Y}",            # The data date
        "info": percentile_meaning(pct["percentile"]),  # What the percentile means, in words
    })

    spot_spread = brent_wti_spot_history(spot)     # Tile 5: the Brent-WTI spot spread, every day both exist
    tiles.append({                                 # e.g. BRENT-WTI SPOT | +19.73 $/bbl | ▼ -1.88 vs 26 Oct | 27 Oct 2026
        "label": "Brent-WTI spot",                 # Which number
        "value": f"{spot_spread.iloc[-1]:+.2f}",   # The latest spread
        "unit": "$/bbl",                           # Its unit
        "detail": change_text(spot_spread.iloc[-1] - spot_spread.iloc[-2], spot_spread.index[-2]),  # Change on EIA's previous day
        "date": f"{spot_spread.index[-1]:%d %b %Y}",  # EIA's latest day
        "info": ("Physical Brent (seaborne crude) minus WTI (US inland crude at Cushing). Usually a few dollars, "  # What it is...
                 "roughly the cost of getting US crude to export markets; wider means seaborne crude is scarcer. "  # ...what moves it...
                 "EIA publishes a few days late."),  # ...and why its date is older
    })

    db = dated_brent_vs_future(spot, brent_future) # Tile 6: physical vs futures, on the latest date both sources have
    tiles.append({                                 # e.g. DATED BRENT VS FUTURE | +9.22 $/bbl | spot above future | 27 Oct 2026
        "label": "Dated Brent vs future",          # Which number
        "value": f"{db['spread']:+.2f}",           # Its value
        "unit": "$/bbl",                           # Its unit
        "detail": "spot above future" if db["spread"] > 0 else "spot below future",  # Plain-English reading
        "date": f"{db['date']:%d %b %Y}",          # The shared date
        "info": physical_meaning(db["spread"]),    # What the sign means, in words
    })
    return tiles                                   # Hand back all six


def summary_markdown(rows, charts, run_time, image_folder):
    """Today's rows, charts and notes as a Markdown section.

    rows         -- from summary_rows()
    charts       -- the list of chart details from charts.save_all_charts()
    run_time     -- when this run happened, to stamp the summary
    image_folder -- the path from the Markdown file to docs/charts/: "docs/charts/" for README.md
                    (top folder) and "../docs/charts/" for output/summary.md (".." means "one folder up")
    Returns the section as one string, with no title, so it can go into both files.
    The chart images don't contain their titles, so each title, subtitle, note and source is written around its image.
    """
    lines = [                                      # The section is built up here, one line at a time
        f"Run at {run_time:%d %b %Y %H:%M} UK time. Prices in $/bbl. "  # When it ran and the units...
        "Every row shows the date its prices come from.",  # ...and the date rule
        "",                                        # Blank line (Markdown needs these between blocks)
        "### Today's numbers",                     # Sub-heading
        "",                                        # Blank line
        "| Measure | Value | Reading | Data date | Working |",  # Table header row
        "|---|---:|---|---|---|",                  # Divider row; ---: right-aligns the Value column so decimals line up
    ]
    for row in rows:                               # One table line per row
        lines.append(f"| {row['measure']} | {row['value']} | {row['reading']} | {row['date']} | {row['working']} |")  # Columns separated by |

    lines += ["", "### Charts", ""]                # Charts sub-heading, with blank lines around it
    for chart in charts:                           # Each chart in turn
        lines.append(f"**Figure {chart['number']}: {chart['title']}**  ")  # Bold title; two trailing spaces = a line break in Markdown
        lines.append(chart["subtitle"])            # What's plotted and the units
        lines.append("")                           # Blank line
        lines.append(f"![Figure {chart['number']}]({image_folder}{chart['path'].name})")  # The image
        lines.append("")                           # Blank line
        if chart["note"]:                          # If the chart has a note...
            lines.append(f"*Note: {chart['note']}*  ")  # ...show it in italics, with a line break after
        lines.append(f"*Source: {chart['source']}*")  # The source line, in italics
        lines.append("")                           # Blank line before the next chart

    lines += ["### Notes", ""]                     # Notes sub-heading
    lines += [f"- {note}" for note in NOTES]       # One bullet point per note
    return "\n".join(lines) + "\n"                 # Join into one string, ending with a newline


def read_commentary():
    """Read Toby's commentary from commentary.txt as a list of paragraphs.

    Takes no inputs. Returns a list of strings, one per paragraph (empty if there's no commentary yet).
    Rules for the file: a blank line starts a new paragraph, and lines starting with # are notes
    to yourself that never appear on the page.
    """
    if not COMMENTARY_FILE.exists():               # No file yet...
        return []                                  # ...so no commentary
    paragraphs = []                                # Finished paragraphs get collected here
    current = []                                   # Lines of the paragraph being read right now
    for line in COMMENTARY_FILE.read_text(encoding="utf-8").splitlines():  # Go through the file line by line
        text = line.strip()                        # Remove spaces at either end
        if text.startswith("#"):                   # A note to yourself...
            continue                               # ...skip it
        if text:                                   # A line with words on it...
            current.append(text)                   # ...belongs to the current paragraph
        elif current:                              # A blank line after some words...
            paragraphs.append(" ".join(current))   # ...ends the paragraph: join its lines with spaces
            current = []                           # ...and start a fresh one
    if current:                                    # The file may end without a blank line...
        paragraphs.append(" ".join(current))       # ...so keep the last paragraph too
    return paragraphs                              # Hand back the paragraphs


def write_html(rows, charts, tiles, run_time, interactive=None):
    """Write docs/index.html: the dashboard.

    rows     -- from summary_rows()
    charts   -- the list of chart details from charts.save_all_charts()
    tiles    -- from headline_tiles()
    run_time -- when this run happened, shown in the masthead
    interactive -- optional: figure number -> Plotly HTML snippet from interactive.build_interactive(); charts
                   without one are shown as their static SVG
    Returns the path of the saved page.
    Layout: navy masthead, six headline tiles, then a chart grid (Figure 1 full width, the rest in pairs) beside a
    commentary sidebar, then the full numbers table. Every piece of text goes through html.escape, so characters
    like < or & in the commentary can't break the page.
    """
    esc = html.escape                              # Short name for the escaping function, used many times below
    version = f"{run_time:%Y%m%d%H%M}"             # A stamp added to each chart's address so browsers fetch the new image, not an old saved copy
    paragraphs = read_commentary()                 # Toby's commentary, if any
    interactive = interactive or {}                # No interactive charts given: use an empty dictionary (every chart shown static)

    page = [                                       # The page is built up here, one line at a time
        "<!DOCTYPE html>",                         # Tells the browser this is a modern HTML page
        '<html lang="en-GB">',                     # The page is in British English
        "<head>",                                  # The head holds information about the page, not shown directly
        '<meta charset="utf-8">',                  # The text encoding, so symbols like ▲ and – display correctly
        '<meta name="viewport" content="width=device-width, initial-scale=1">',  # Fit the page to phone screens
        "<title>Oil Curve Tracker</title>",        # The text on the browser tab
        '<meta name="description" content="Daily Brent and WTI futures curves, spreads and backwardation, with commentary.">',  # Summary for search engines
        f"<style>{STYLE}</style>",                 # The styling defined at the top of this file
        PLOTLY_SCRIPT if interactive else "",      # Load Plotly's JavaScript once, but only if there are interactive charts
        "</head>",                                 # End of the head
        "<body>",                                  # The visible page starts here
        '<header class="masthead"><div class="wrap">',  # The navy band across the top
        "<div>",                                   # Left side of the band
        '<p class="label">Crude oil | Daily curve monitor</p>',  # Small gold label above the title
        "<h1>Oil Curve Tracker</h1>",              # Page title
        '<p class="subtitle">Brent and WTI futures curves, spreads and backwardation. Updated every weekday at 22:30 UK time.</p>',  # What the page is
        "</div>",                                  # End of the left side
        f'<div class="stamp">Last updated<strong>{run_time:%d %b %Y, %H:%M}</strong>UK time</div>',  # Right side: when it was made
        "</div></header>",                         # End of the band
        '<main class="wrap">',                     # The main content
        '<section class="tiles">',                 # The six headline tiles
    ]
    for tile in tiles:                             # One tile per headline number
        page += [                                  # Each tile: label, number with unit, change or reading, date
            '<div class="tile">',                  # Start of the tile
            f'<p class="tile-label">{esc(tile["label"])}</p>',  # e.g. "BRENT M1 · JAN-27"
            f'<p class="tile-value">{esc(tile["value"])}<span class="tile-unit">{esc(tile["unit"])}</span></p>',  # e.g. "104.77 $/bbl"
            f'<p class="tile-detail">{esc(tile["detail"])}</p>',  # e.g. "▼ -8.66 vs 30 Oct"
            f'<p class="tile-date">{esc(tile["date"])}</p>',  # e.g. "02 Nov 2026"
            f'<p class="tile-info">{esc(tile["info"])}</p>',  # What it measures and what today's number means
            "</div>",                              # End of the tile
        ]
    page += ["</section>", '<div class="layout">', '<div class="charts">']  # End the tiles; start the charts grid beside the sidebar

    for chart in charts:                           # One card per chart
        wide = " wide" if chart["number"] == 1 else ""  # Figure 1 spans both columns
        alt = f"Figure {chart['number']}: {chart['title']}. {chart['subtitle']}"  # Description read aloud by screen readers
        static = f"charts/{chart['path'].name}?v={version}"  # Address of the static SVG version of this chart
        image = f'<img src="{static}" alt="{esc(alt)}" loading="lazy">'  # The static chart as an image
        page += [                                  # The card: label, takeaway title, subtitle, chart, note, source
            f'<article class="card{wide}">',       # Start of the card
            f'<p class="fig">Figure {chart["number"]}</p>',  # "FIGURE 1"
            f"<h3>{esc(chart['title'])}</h3>",     # The takeaway title, generated from the data
            f'<p class="sub">{esc(chart["subtitle"])}</p>',  # What's plotted and the units
        ]
        if chart["number"] in interactive:         # An interactive version exists...
            page += [                              # ...so show it, keeping the static one as a backup
                f'<div class="plot">{interactive[chart["number"]]}</div>',  # The Plotly chart (hover, drag to zoom)
                f"<noscript>{image}</noscript>",   # If the browser blocks JavaScript, show the static chart instead
                f'<p class="foot hint">Hover for exact values; drag to zoom in, double-click to reset. '  # How to use it...
                f'<a href="{static}" target="_blank">Static version</a></p>',  # ...and a link to the SVG
            ]
        else:                                      # No interactive version: the static chart, clickable to open full size
            page.append(f'<a href="{static}" target="_blank" title="Open full size">{image}</a>')  # Opens in a new tab
        if chart["note"]:                          # If the chart has a note...
            page.append(f'<p class="foot">Note: {esc(chart["note"])}</p>')  # ...show it under the image
        page += [f'<p class="foot">Source: {esc(chart["source"])}</p>', "</article>"]  # Source line, then end the card
    page.append("</div>")                          # End of the charts grid

    page += ['<aside class="side">', '<div class="card">', "<h2>Commentary</h2>"]  # The sidebar, starting with the commentary card
    if paragraphs:                                 # If there's commentary...
        page.append(f'<p class="dated">{esc(paragraphs[0])}</p>')  # ...its first line (the date it was written) in bold navy
        page += [f"<p>{esc(p)}</p>" for p in paragraphs[1:]]  # ...then one <p> (paragraph) per paragraph, escaped
    else:                                          # Otherwise...
        page.append("<p>No commentary yet.</p>")   # ...say so rather than leave a gap
    page.append('<p class="foot">Written by hand, so it changes only when I update it; '  # Make clear the commentary isn't automatic...
                "the numbers and charts update every weekday.</p>")  # ...so readers check the dates
    page += ["</div>", '<div class="card">', "<h2>Notes on method</h2>", "<ul>"]  # End commentary; start the method notes card
    page += [f"<li>{esc(note)}</li>" for note in NOTES]  # One bullet per note
    page += ["</ul>", "</div>", "</aside>", "</div>"]  # End the notes, the sidebar and the layout

    page += [                                      # The full numbers table, full width at the bottom
        '<section class="card numbers">',          # Start of the table card
        "<h2>All numbers</h2>",                    # Its heading
        '<div class="table-wrap"><table>',         # Wrapper that lets the table scroll sideways on a phone
        '<thead><tr><th>Measure</th><th class="num">Value</th><th>Reading</th><th>Data date</th><th>Working</th></tr></thead>',  # Header row
        "<tbody>",                                 # Start of the table body
    ]
    for row in rows:                               # One table row per number
        page.append(                               # Each cell's text is escaped before it goes in
            f"<tr><td>{esc(row['measure'])}</td><td class=\"num\">{esc(row['value'])}</td>"  # Measure and value...
            f"<td>{esc(row['reading'])}</td><td>{esc(row['date'])}</td><td>{esc(row['working'])}</td></tr>"  # ...reading, date, working
        )                                          # End of this row
    page += ["</tbody>", "</table></div>", "</section>", "</main>"]  # Close the table, its card and the main content

    page += [                                      # The footer at the bottom of the page
        '<footer class="wrap">',                   # Start of the footer
        f'<p>Data: <a href="https://www.eia.gov/opendata/">EIA Open Data</a> and NYMEX via Yahoo Finance. '  # Data sources...
        f'Code: <a href="{REPO_URL}">GitHub</a>. For learning purposes; not investment advice.</p>',  # ...the code, and a disclaimer
        "</footer>",                               # End of the footer
        "</body>",                                 # End of the visible page
        "</html>",                                 # End of the document
    ]
    REPORT_FILE.write_text("\n".join(page) + "\n", encoding="utf-8")  # Save the page, one element per line
    return REPORT_FILE                             # Tell the caller where it went
