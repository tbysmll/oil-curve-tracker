"""
report.py - turns the tracker's results into things people read.

  summary_rows()      - today's numbers as table rows, each with its data date (built once, used everywhere)
  summary_markdown()  - those rows plus the charts as Markdown, for README.md and output/summary.md
  write_html()        - docs/index.html, the single-page web report that GitHub Pages publishes

The web page also shows Toby's own commentary, read from commentary.txt (edited by hand).
It's one self-contained HTML file with its styling built in and no JavaScript, so it loads fast anywhere.
"""

import html                                        # html.escape makes text safe to place inside a web page
from config import BASE_DIR, DOCS_DIR, REPO_URL    # Folders, and the GitHub link for the page footer
from spreads import curve_spreads, brent_wti_spot, dated_brent_vs_future, wti_m1m2_percentile  # The calculations

COMMENTARY_FILE = BASE_DIR / "commentary.txt"      # Toby's hand-written commentary
REPORT_FILE = DOCS_DIR / "index.html"              # The web page; "index.html" is the file a website shows by default

CHART_CAPTIONS = {                                 # A one-line caption for each chart, keyed by its file name
    "curves": "Each futures curve today (solid) against the same contracts one month earlier (dashed).",  # Chart 1
    "brent_wti_spread": "Brent minus WTI spot price (EIA) over the past two years.",  # Chart 2
    "m1_m6_fixed": "Today's M1 minus M6 contracts, held fixed, over the past six months.",  # Chart 3
    "wti_m1m2_history": "How often each WTI M1-M2 value occurred from 2010 to 2024, with today's value marked.",  # Chart 4
}                                                  # End of the captions

NOTES = [                                          # Caveats shown under the numbers in every report
    "Brent and WTI curves can come from different days: each uses its latest day with all 12 contracts priced.",  # curve_on() behaviour
    "If the tracker ran during US trading hours, the latest futures prices are live rather than closing prices.",  # Yahoo live prices
    "EIA spot prices run a few days behind; the WTI percentile deliberately compares today with 2010-2024.",  # EIA lag and the agreed exception
]                                                  # End of the notes

# The page's styling (CSS). Each line sets how one kind of element looks.
STYLE = """
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #222; background: #fff; line-height: 1.55; } /* Clean system font, dark text on white */
main { max-width: 920px; margin: 0 auto; padding: 32px 20px 48px; }  /* One centred column, comfortable to read */
h1 { margin: 0 0 4px; font-size: 1.9rem; }                            /* Page title */
h2 { margin: 40px 0 12px; font-size: 1.3rem; padding-bottom: 6px; border-bottom: 1px solid #ddd; }  /* Section headings with a thin line under them */
.subtitle, .meta, .note { color: #555; }                               /* Secondary text in mid grey */
.meta, .note { font-size: 0.9rem; }                                    /* ...and slightly smaller */
.table-wrap { overflow-x: auto; }                                      /* On a phone the table scrolls sideways instead of squashing */
table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }  /* Full-width table with single-line borders */
th, td { padding: 7px 10px; text-align: left; vertical-align: top; border-bottom: 1px solid #e5e5e5; }  /* Cell spacing and faint row lines */
th { background: #f6f6f6; font-weight: 600; }                          /* Light grey header row */
td:first-child { min-width: 8em; }                                     /* Wide enough that "Brent M1-M12" never breaks at its hyphen */
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }  /* Numbers right-aligned so the decimals line up */
.commentary p { margin: 0 0 14px; }                                    /* Space between commentary paragraphs */
figure { margin: 28px 0; }                                             /* Space around each chart */
figure img { width: 100%; height: auto; border: 1px solid #eee; }      /* Charts fill the column width */
figcaption { margin-top: 6px; color: #555; font-size: 0.9rem; }        /* Caption under each chart */
footer { margin-top: 48px; color: #666; font-size: 0.85rem; }          /* Small grey footer */
a { color: #1f4e79; }                                                  /* Links in the Brent blue */
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


def summary_markdown(rows, chart_paths, run_time, image_folder):
    """Today's rows, charts and notes as a Markdown section.

    rows         -- from summary_rows()
    chart_paths  -- the saved chart files from charts.save_all_charts()
    run_time     -- when this run happened, to stamp the summary
    image_folder -- the path from the Markdown file to docs/charts/: "docs/charts/" for README.md
                    (top folder) and "../docs/charts/" for output/summary.md (".." means "one folder up")
    Returns the section as one string, with no title, so it can go into both files.
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
    for path in chart_paths:                       # Each saved chart in turn
        lines.append(f"![{path.stem}]({image_folder}{path.name})")  # Markdown image, e.g. ![curves](docs/charts/curves.png)
        lines.append("")                           # Blank line so each chart sits on its own

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


def write_html(rows, chart_paths, run_time):
    """Write docs/index.html: the single-page web report.

    rows        -- from summary_rows()
    chart_paths -- the saved chart files from charts.save_all_charts()
    run_time    -- when this run happened, shown at the top of the page
    Returns the path of the saved page.
    Every piece of text goes through html.escape, so characters like < or & in the commentary
    can't break the page.
    """
    esc = html.escape                              # Short name for the escaping function, used many times below
    version = f"{run_time:%Y%m%d%H%M}"             # A stamp added to each chart's address so browsers fetch the new image, not an old saved copy
    paragraphs = read_commentary()                 # Toby's commentary, if any

    page = [                                       # The page is built up here, one line at a time
        "<!DOCTYPE html>",                         # Tells the browser this is a modern HTML page
        '<html lang="en-GB">',                     # The page is in British English
        "<head>",                                  # The head holds information about the page, not shown directly
        '<meta charset="utf-8">',                  # The text encoding, so symbols like £ and – display correctly
        '<meta name="viewport" content="width=device-width, initial-scale=1">',  # Fit the page to phone screens
        "<title>Oil Curve Tracker</title>",        # The text on the browser tab
        '<meta name="description" content="Daily Brent and WTI futures curves, spreads and backwardation, with commentary.">',  # Summary for search engines
        f"<style>{STYLE}</style>",                 # The styling defined at the top of this file
        "</head>",                                 # End of the head
        "<body>",                                  # The visible page starts here
        "<main>",                                  # The main content column
        "<header>",                                # The top of the page
        "<h1>Oil Curve Tracker</h1>",              # Page title
        '<p class="subtitle">The shape of the Brent and WTI crude oil futures curves, updated every weekday at 22:30 UK time.</p>',  # What the page is
        f'<p class="meta">Last updated {run_time:%d %b %Y, %H:%M} UK time. Prices in $/bbl. '  # When it was made...
        "Every number shows the date its prices come from.</p>",  # ...and the date rule
        "</header>",                               # End of the top section
        "<section>",                               # The numbers section
        "<h2>Today's numbers</h2>",                # Its heading
        '<div class="table-wrap">',                # Wrapper that lets the table scroll sideways on a phone
        "<table>",                                 # Start of the table
        '<thead><tr><th>Measure</th><th class="num">Value</th><th>Reading</th><th>Data date</th><th>Working</th></tr></thead>',  # Header row
        "<tbody>",                                 # Start of the table body
    ]
    for row in rows:                               # One table row per number
        page.append(                               # Each cell's text is escaped before it goes in
            f"<tr><td>{esc(row['measure'])}</td><td class=\"num\">{esc(row['value'])}</td>"  # Measure and value...
            f"<td>{esc(row['reading'])}</td><td>{esc(row['date'])}</td><td>{esc(row['working'])}</td></tr>"  # ...reading, date, working
        )                                          # End of this row
    page += ["</tbody>", "</table>", "</div>", "</section>"]  # Close the table and the section

    page += ['<section class="commentary">', "<h2>Commentary</h2>"]  # The commentary section and its heading
    if paragraphs:                                 # If there's commentary...
        page += [f"<p>{esc(p)}</p>" for p in paragraphs]  # ...one <p> (paragraph) per paragraph, escaped
    else:                                          # Otherwise...
        page.append('<p class="note">No commentary yet.</p>')  # ...say so rather than leave a gap
    page.append('<p class="note">Written by hand, so it changes only when I update it; '  # Make clear the commentary isn't automatic...
                "the numbers and charts update automatically every weekday.</p>")  # ...so readers check the dates
    page.append("</section>")                      # End of the commentary section

    page += ["<section>", "<h2>Charts</h2>"]       # The charts section and its heading
    for path in chart_paths:                       # Each chart in turn
        caption = CHART_CAPTIONS.get(path.stem, "")  # Its caption ("" if it doesn't have one)
        page += [                                  # A figure: the image with its caption underneath
            "<figure>",                            # Start of the figure
            f'<img src="charts/{path.name}?v={version}" alt="{esc(caption)}" loading="lazy">',  # The image; alt text describes it for screen readers
            f"<figcaption>{esc(caption)}</figcaption>",  # The caption
            "</figure>",                           # End of the figure
        ]
    page.append("</section>")                      # End of the charts section

    page += ["<section>", "<h2>Notes on method</h2>", "<ul>"]  # The notes section, as a bulleted list
    page += [f"<li>{esc(note)}</li>" for note in NOTES]  # One bullet per note
    page += ["</ul>", "</section>"]                # End of the list and the section

    page += [                                      # The footer at the bottom of the page
        "<footer>",                                # Start of the footer
        f'<p>Data: <a href="https://www.eia.gov/opendata/">EIA Open Data</a> and Yahoo Finance. '  # Data sources...
        f'Code: <a href="{REPO_URL}">GitHub</a>. For learning purposes; not investment advice.</p>',  # ...the code, and a disclaimer
        "</footer>",                               # End of the footer
        "</main>",                                 # End of the content column
        "</body>",                                 # End of the visible page
        "</html>",                                 # End of the document
    ]
    REPORT_FILE.write_text("\n".join(page) + "\n", encoding="utf-8")  # Save the page, one element per line
    return REPORT_FILE                             # Tell the caller where it went
