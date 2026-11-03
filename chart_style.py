"""
chart_style.py - the house style for every chart, modelled on a sell-side bank research note.

Every chart in charts.py takes its colours, font, size, layout and labelling from here, so they
all look the same. To change the look of every chart at once, change it in this file only.

The layout of each figure, top to bottom:
  Figure N: <takeaway title, bold>          <- what the chart shows, generated from the data
  <one-line grey subtitle: what's plotted and the units>
  [ the chart itself, lines labelled at their right-hand end, today's value as a gold dot ]
  Source: ... Data as of DD Mon YYYY.       <- small grey text, bottom-left
"""

import matplotlib.pyplot as plt                    # pyplot creates figures and chart areas
import matplotlib.dates as mdates                  # Formats dates along an axis
from matplotlib import font_manager                # Lets us check which fonts are installed

# ---------------------------------------------------------------------------
# Palette: these five colours (on a white background) are the only ones the charts use
# ---------------------------------------------------------------------------
NAVY = "#002B5C"         # Primary colour: Brent, and the main line on single-series charts
MID_BLUE = "#4F81BD"     # WTI
GOLD = "#C9A227"         # Highlights: today's value
DARK_GREY = "#595959"    # All text, and secondary series (e.g. "one month earlier")
LIGHT_GREY = "#D9D9D9"   # Gridlines and zero lines
WHITE = "#FFFFFF"        # Background

MARKET_COLOURS = {"Brent": NAVY, "WTI": MID_BLUE}  # Each market always gets the same colour, on every chart

# ---------------------------------------------------------------------------
# Size, font and date format
# ---------------------------------------------------------------------------
FIGSIZE = (10, 5.5)      # Every chart is 10 x 5.5 inches...
DPI = 200                # ...saved at 200 dots per inch, i.e. 2000 x 1100 pixels
DATE_FORMAT = "%b-%y"    # Dates written like "Nov-26"
FONT_PREFERENCE = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]  # First one installed wins; Liberation Sans
                         # is a free Arial look-alike found on Linux (e.g. GitHub's servers); DejaVu Sans comes with matplotlib

# ---------------------------------------------------------------------------
# Layout, as fractions of the figure (0 = left/bottom edge, 1 = right/top edge)
# ---------------------------------------------------------------------------
TEXT_X = 0.02            # Left edge of the title, subtitle and source line
TITLE_Y = 0.96           # Top of the bold title
SUBTITLE_Y = 0.895       # Top of the grey subtitle
SOURCE_Y = 0.02          # Bottom of the source line
PLOT_LEFT = 0.08         # Left edge of the chart area (leaves room for the y-axis numbers and label)
PLOT_RIGHT = 0.88        # Right edge of the chart area (leaves room for the line-end labels)
PLOT_TOP = 0.80          # Top of the chart area (leaves room for the title and subtitle)
PLOT_BOTTOM = 0.16       # Bottom of the chart area (leaves room for the dates and the source line)
PLOT_BOTTOM_WITH_NOTE = 0.21  # Bottom of the chart area when a note sits between the dates and the source line
NOTE_Y = 0.065           # Bottom of that note


def pick_font():
    """Return the first font in FONT_PREFERENCE that's installed on this computer.

    Takes no inputs. Returns a font name such as "Arial".
    Exists so the same code gives Arial on Windows and the closest match elsewhere, without warnings.
    """
    installed = {font.name for font in font_manager.fontManager.ttflist}  # Names of every font matplotlib can find
    for name in FONT_PREFERENCE:                   # Try each preferred font in order...
        if name in installed:                      # ...and use the first one that's installed
            return name                            # e.g. "Arial"
    return "DejaVu Sans"                           # Always available: it ships with matplotlib


def rc_params():
    """The matplotlib settings that give every chart the house look.

    Takes no inputs. Returns a dictionary of matplotlib settings ("rcParams").
    Used with plt.rc_context(rc_params()), which applies them only while one chart is being drawn.
    """
    return {                                       # Each setting below changes one default of matplotlib
        "font.family": pick_font(),                # Arial (or the nearest installed match)
        "font.size": 10,                           # Default text size in points
        "text.parse_math": False,                  # Treat $ as a plain dollar sign: otherwise text between two $ signs
                                                   # (e.g. "$/bbl ... $/bbl") is read as a maths formula and garbled
        "text.color": DARK_GREY,                   # Default text colour
        "axes.labelcolor": DARK_GREY,              # Axis label colour
        "axes.edgecolor": DARK_GREY,               # Colour of the left and bottom axis lines
        "axes.linewidth": 0.8,                     # Thin axis lines
        "axes.spines.top": False,                  # No border along the top...
        "axes.spines.right": False,                # ...or down the right-hand side
        "axes.grid": True,                         # Gridlines on...
        "axes.grid.axis": "y",                     # ...horizontal only (no vertical gridlines)
        "axes.axisbelow": True,                    # Gridlines drawn behind the data
        "grid.color": LIGHT_GREY,                  # Light grey gridlines
        "grid.linewidth": 0.8,                     # Thin gridlines
        "xtick.color": DARK_GREY,                  # Tick marks and numbers along the bottom
        "ytick.color": DARK_GREY,                  # Tick marks and numbers up the side
        "xtick.major.size": 3,                     # Short tick marks...
        "ytick.major.size": 0,                     # ...and none on the y-axis (the gridlines do that job)
        "lines.linewidth": 2,                      # Default line thickness
        "legend.frameon": False,                   # If a legend is ever needed, no box around it
        "figure.facecolor": WHITE,                 # White figure background
        "axes.facecolor": WHITE,                   # White chart-area background
        "savefig.facecolor": WHITE,                # Saved files have a white background, never transparent
    }


def new_figure(nrows=1, ncols=1, **kwargs):
    """Create a blank figure at the house size, with room left for the title, subtitle and source.

    nrows, ncols -- how many chart areas, in rows and columns (most charts have one)
    **kwargs     -- any extra plt.subplots options, e.g. sharey=True
    Returns (fig, axes): the figure and its chart area(s).
    """
    fig, axes = plt.subplots(nrows, ncols, figsize=FIGSIZE, **kwargs)  # The figure and its chart area(s)
    fig.subplots_adjust(left=PLOT_LEFT, right=PLOT_RIGHT, top=PLOT_TOP, bottom=PLOT_BOTTOM,  # Fixed margins...
                        wspace=0.30, hspace=0.35)  # ...and spacing between panels, so every chart lines up the same way
    return fig, axes                               # Hand them back


def add_titles(fig, number, takeaway, subtitle):
    """Write the numbered, left-aligned bold title and the grey subtitle at the top of the figure.

    fig      -- the figure
    number   -- the figure number, e.g. 1
    takeaway -- what the chart shows, e.g. "Brent curve in steep backwardation"
    subtitle -- what's plotted and the units, e.g. "Futures price by delivery month, $/bbl"
    Returns nothing.
    """
    fig.text(TEXT_X, TITLE_Y, f"Figure {number}: {takeaway}",  # "Figure 1: ..."
             ha="left", va="top", fontsize=13, fontweight="bold", color=NAVY)  # Left-aligned, bold, navy
    fig.text(TEXT_X, SUBTITLE_Y, subtitle,         # The subtitle, just below the title
             ha="left", va="top", fontsize=10, color=DARK_GREY)  # Left-aligned, regular weight, grey


def add_source(fig, sources, as_of):
    """Write the source line in small grey text at the bottom-left of the figure.

    fig     -- the figure
    sources -- where the data came from, e.g. "EIA, NYMEX via Yahoo Finance"
    as_of   -- the data date(s) as text, e.g. "02 Nov 2026"
    Returns nothing.
    """
    fig.text(TEXT_X, SOURCE_Y, f"Source: {sources}. Data as of {as_of}.",  # "Source: ... Data as of ..."
             ha="left", va="bottom", fontsize=8, color=DARK_GREY)  # Small, grey, bottom-left


def add_note(fig, text):
    """Write a short grey note between the chart and the source line (e.g. a warning about the data).

    fig  -- the figure
    text -- the note
    Returns nothing. Raises the bottom of the chart area slightly to make room for the note.
    """
    fig.subplots_adjust(bottom=PLOT_BOTTOM_WITH_NOTE)  # Lift the chart area so the note fits under the dates
    fig.text(TEXT_X, NOTE_Y, text, ha="left", va="bottom", fontsize=8, color=DARK_GREY)  # Small grey note, above the source line


def style_axes(ax, ylabel="$/bbl", dates=False):
    """Finish one chart area: y-axis label and, for time series, dates written like "Nov-26".

    ax     -- the chart area
    ylabel -- the y-axis label ("" for none, e.g. on a right-hand panel that shares the left one's axis)
    dates  -- True if the x-axis holds dates
    Returns nothing. Borders and gridlines are already handled by rc_params().
    """
    ax.set_ylabel(ylabel)                          # e.g. "$/bbl"
    if dates:                                      # For charts over time...
        ax.xaxis.set_major_formatter(mdates.DateFormatter(DATE_FORMAT))  # ...write dates as "Nov-26"


def label_line_end(ax, x, y, text, colour, dy=0):
    """Write a line's name just to the right of its last point, instead of using a legend box.

    ax     -- the chart area
    x, y   -- the line's last point
    text   -- the label, e.g. "Brent"
    colour -- the line's colour, so the label is clearly tied to its line
    dy     -- optional nudge up (+) or down (-) in points, to stop two labels overlapping
    Returns nothing.
    """
    ax.annotate(text, (x, y), xytext=(8, dy), textcoords="offset points",  # 8 points right of the end of the line
                va="center", ha="left", fontsize=9, fontweight="bold", color=colour,  # Bold, in the line's colour
                annotation_clip=False)             # Allow the label to sit in the margin outside the chart area


def mark_latest(ax, x, y, text, dx=8, dy=0, ha="left"):
    """Mark today's value with a small gold dot and its number.

    ax       -- the chart area
    x, y     -- where today's value sits on the chart
    text     -- the number to show, e.g. "105.75"
    dx, dy   -- where to put the number relative to the dot, in points
    ha       -- "left" puts the number to the right of that spot, "right" to the left
    Returns nothing.
    """
    ax.scatter([x], [y], s=28, color=GOLD, zorder=5)  # The gold dot, drawn on top of the line (zorder)
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points",  # The number, nudged off the dot
                va="center", ha=ha, fontsize=9, fontweight="bold", color=DARK_GREY,  # Bold grey text
                annotation_clip=False)             # Allow it to sit in the margin if needed


def label_latest(ax, x, y, text, colour, dy=0):
    """For a line over time: a gold dot on its latest point, with the line's name and latest value beside it.

    ax     -- the chart area
    x, y   -- the latest point (last date, last value)
    text   -- name and value together, e.g. "Brent +11.71"
    colour -- the line's colour, so the label is clearly tied to its line
    dy     -- optional nudge up (+) or down (-) in points, from label_offsets(), to stop labels overlapping
    Returns nothing. Replaces a legend: the label sits where the reader's eye ends up.
    """
    ax.scatter([x], [y], s=28, color=GOLD, zorder=5)  # The gold dot, drawn on top of the line
    label_line_end(ax, x, y, text, colour, dy=dy)  # The name and value just to its right


def label_offsets(ax, ys, min_gap=12):
    """Work out how far to nudge line-end labels so that none sit closer than `min_gap` points apart.

    ax      -- the chart area (its scale is needed to turn $/bbl into distance on the page)
    ys      -- the heights of the labels in data units, e.g. [11.71, 8.75]
    min_gap -- the smallest allowed vertical gap between labels, in points (a 9-point label needs about 12)
    Returns a list of nudges in points, one per label, in the same order as ys (0 = no nudge needed).
    """
    to_points = 72 / ax.figure.dpi                 # 72 points per inch; dpi is pixels per inch, so this turns pixels into points
    heights = [ax.transData.transform((0, y))[1] * to_points for y in ys]  # Each label's height on the page, in points
    order = sorted(range(len(ys)), key=lambda i: heights[i])  # Label numbers from lowest to highest on the page
    placed = list(heights)                         # Where each label will end up; starts where it would naturally sit
    for previous, current in zip(order, order[1:]):  # Walk up the labels, each one with the one just below it
        if placed[current] - placed[previous] < min_gap:  # Too close to the one below...
            placed[current] = placed[previous] + min_gap  # ...so push it up to exactly min_gap above
    return [placed[i] - heights[i] for i in range(len(ys))]  # Nudge = where it ends up minus where it started


def save(fig, path):
    """Save the figure as a PNG at the house size and resolution, with a white background, then close it.

    fig  -- the finished figure
    path -- where to save it, e.g. docs/charts/curves.png
    Returns the path.
    No "tight" trimming, so every chart comes out exactly 10 x 5.5 inches (2000 x 1100 pixels).
    """
    fig.savefig(path, dpi=DPI, facecolor=WHITE)    # Write the PNG
    plt.close(fig)                                 # Free the memory
    return path                                    # Tell the caller where it went
