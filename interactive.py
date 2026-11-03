"""
interactive.py - interactive versions of the five dashboard charts, built with Plotly, for the website.

On the dashboard you can hover to see the date and every line's exact value, drag to zoom into a period,
and double-click to zoom back out. The static SVG charts from charts.py are still made for the README and
as a fallback if a visitor's browser blocks JavaScript.

Same house style as chart_style.py (palette, right-hand axis, gold latest-value dot, coloured value tags,
key above the plot) and the same calculations from spreads.py, so the numbers match the static charts exactly.
Each card's title, subtitle, note and source still come from charts.py (chart_info), so they're written once.
"""

import pandas as pd                                # pandas, for date windows
import plotly.graph_objects as go                  # Plotly's chart building blocks (figures, lines, bars)
from plotly.subplots import make_subplots          # Plotly's tool for figures with more than one panel
from plotly.offline import get_plotlyjs_version    # The version of Plotly's JavaScript that matches this Python library
import chart_style as style                        # The house palette
from charts import month_label, same_contracts_earlier  # Shared helpers, so both chart versions use the same contracts and labels
from spreads import (                              # The calculations behind the charts
    wti_m1m2_history,                              # The daily WTI M1-M2 history from EIA
    time_spreads,                                  # Today's M1-M2 etc. from a curve
    brent_wti_spot_history,                        # The daily Brent-WTI spot spread from EIA
    fixed_contract_spread,                         # The spread between two fixed contracts over time
    front_month_spread,                            # Brent and WTI front-month futures side by side, and their gap
)

# The <script> line the web page needs once, in its <head>, to load Plotly's JavaScript from Plotly's own site.
# Pinned to the exact version that matches the installed Python library, so the two always agree.
PLOTLY_SCRIPT = f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js" charset="utf-8"></script>'

CONFIG = {"displayModeBar": False, "responsive": True}  # No toolbar (drag to zoom and double-click to reset still work); resize with the card
CARD_HEIGHT = 300                                  # Height of a half-width chart, in screen pixels
WIDE_HEIGHT = 320                                  # Height of the full-width Figure 1
FONT = "Arial, Helvetica, 'Liberation Sans', sans-serif"  # Same font as the page and the static charts


def house_layout(fig, height):
    """Apply the house look to a Plotly figure: palette, font, right-hand axis, light gridlines, key above the plot.

    fig    -- the Plotly figure
    height -- its height in screen pixels
    Returns nothing (the figure is changed in place).
    """
    fig.update_layout(                             # Settings for the whole figure
        height=height,                             # Fixed height; the width follows the card
        margin={"l": 8, "r": 96, "t": 30, "b": 30},  # Small margins, with room on the right for axis numbers and value tags
        paper_bgcolor=style.WHITE,                 # White background around the plot...
        plot_bgcolor=style.WHITE,                  # ...and behind it
        font={"family": FONT, "size": 12, "color": style.DARK_GREY},  # House font and text colour
        legend={"orientation": "h", "x": 0, "y": 1.02, "xanchor": "left", "yanchor": "bottom",  # Key on one row, above the plot...
                "font": {"size": 11}},             # ...in small text
        hovermode="x unified",                     # Hovering shows one box with every line's value on that date
        hoverlabel={"bgcolor": style.WHITE, "bordercolor": style.LIGHT_GREY,  # Hover box: white with a light border...
                    "font": {"family": FONT, "size": 12, "color": style.DARK_GREY}},  # ...in the house font
    )                                              # End of the whole-figure settings
    fig.update_xaxes(                              # Settings for every x-axis
        showgrid=False,                            # No vertical gridlines
        showline=True, linecolor=style.DARK_GREY, linewidth=1,  # A thin bottom baseline
        ticks="outside", ticklen=3, tickcolor=style.DARK_GREY,  # Short tick marks under the baseline
        tickfont={"size": 11},                     # Small date labels
    )                                              # End of the x-axis settings
    fig.update_yaxes(                              # Settings for every y-axis
        side="right",                              # Numbers on the right, where the latest data is
        showgrid=True, gridcolor=style.LIGHT_GREY, gridwidth=1,  # Light horizontal gridlines
        zeroline=False, showline=False,            # No extra zero line or axis line (added deliberately where wanted)
        tickfont={"size": 11},                     # Small numbers
    )                                              # End of the y-axis settings


def date_axes(fig):
    """For time-series charts: dates along the bottom like "Nov-26", and "03 Nov 2026" at the top of the hover box.

    fig -- the Plotly figure
    Returns nothing.
    """
    fig.update_xaxes(tickformat="%b-%y", hoverformat="%d %b %Y")  # Axis labels like "Nov-26"; hover header like "03 Nov 2026"


def latest_dot(fig, x, y, **where):
    """A small gold dot on a line's latest point (no hover, no key entry).

    fig     -- the Plotly figure
    x, y    -- the latest point
    **where -- which panel it belongs to on multi-panel charts, e.g. row=2, col=1
    Returns nothing.
    """
    fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers",  # A single point drawn as a marker
                             marker={"color": style.GOLD, "size": 8},  # Gold dot
                             showlegend=False, hoverinfo="skip"), **where)  # Not in the key, ignored by hover


def value_tag(fig, y, text, colour, yref="y"):
    """A coloured tag to the right of the axis numbers, showing a line's latest value.

    fig    -- the Plotly figure
    y      -- the value, which sets the tag's height
    text   -- what the tag says, e.g. "+11.71"
    colour -- the line's colour (the tag is filled with it, with white text)
    yref   -- which panel's y-axis: "y" for the first, "y2" for the second, and so on
    Returns nothing.
    """
    fig.add_annotation(x=1, xref="paper", xanchor="left", xshift=40,  # Just past the right edge, beyond the axis numbers
                       y=y, yref=yref,             # At the value's height on that panel's axis
                       text=f"<b>{text}</b>", showarrow=False,  # Bold text, no pointer arrow
                       font={"color": style.WHITE, "size": 11},  # White text...
                       bgcolor=colour, borderpad=2)  # ...on a box in the line's colour


def figure_curves(curves, prices):
    """Figure 1: each market's curve today (solid) and the same contracts one month earlier (dashed), side by side.

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    Returns the Plotly figure. Hover shows each contract's price today and a month earlier.
    """
    fig = make_subplots(rows=1, cols=len(curves), shared_yaxes=True, horizontal_spacing=0.05)  # Two panels, one price scale
    for col, (market, (curve, date)) in enumerate(curves.items(), start=1):  # Each market in its own panel (col = 1, 2)
        colour = style.MARKET_COLOURS[market]      # Navy for Brent, mid blue for WTI
        earlier, earlier_date = same_contracts_earlier(prices[market], curve, date)  # Same contracts a month ago
        labels = [month_label(c) for c in curve.index]  # Delivery months along the bottom, e.g. "Jan-27"
        fig.add_trace(go.Scatter(x=labels, y=earlier.values, mode="lines", name=f"{market} {earlier_date:%d %b}",  # A month earlier, as a plain line...
                                 line={"color": style.DARK_GREY, "width": 1.5, "dash": "dash"},  # ...grey dashes
                                 hovertemplate="%{y:.2f}"), row=1, col=col)  # Hover shows the price
        fig.add_trace(go.Scatter(x=labels, y=curve.values, mode="lines", name=f"{market} {date:%d %b}",  # Today, as a plain line...
                                 line={"color": colour, "width": 2.2},  # ...solid, in the market's colour
                                 hovertemplate="%{y:.2f}"), row=1, col=col)  # Hover shows the price
        latest_dot(fig, labels[0], curve.iloc[0], row=1, col=col)  # Gold dot on today's front month (M1)
        fig.update_xaxes(tickvals=labels[::2], tickangle=0, row=1, col=col)  # Label every other month, level, so they don't crowd
    house_layout(fig, WIDE_HEIGHT)                 # House look
    fig.update_yaxes(showticklabels=False, col=1)  # The left panel shares the right panel's scale, so no numbers in the gap...
    fig.update_yaxes(showticklabels=True, col=2)   # ...and the right panel shows them (Plotly hides them there by default)
    return fig                                     # Hand back the figure


def figure_brent_wti_spread(spot, years=2):
    """Figure 2: the Brent-WTI spot spread from EIA over the past `years` years, with its two-year median.

    spot  -- the table from eia.fetch_spot()
    years -- how many years back from EIA's latest date to show
    Returns the Plotly figure.
    """
    spread = brent_wti_spot_history(spot)          # Daily Brent minus WTI, every day both exist
    recent = spread.loc[spread.index.max() - pd.DateOffset(years=years):]  # Just the last two years
    median = recent.median()                       # The typical spread over the two years

    fig = go.Figure()                              # One panel
    fig.add_hline(y=0, line={"color": style.LIGHT_GREY, "width": 1})  # Zero line: below it, WTI would be dearer than Brent
    fig.add_trace(go.Scatter(x=recent.index, y=[median] * len(recent), name="2-yr median",  # The median, as a flat line...
                             line={"color": style.DARK_GREY, "width": 1.2, "dash": "dash"},  # ...grey dashes
                             hovertemplate="%{y:+.2f}"))  # Hover shows it with a sign
    fig.add_trace(go.Scatter(x=recent.index, y=recent.values, name="Brent minus WTI",  # The daily spread...
                             line={"color": style.NAVY, "width": 1.6},  # ...in navy
                             hovertemplate="%{y:+.2f}"))  # Hover shows it with a sign
    latest_dot(fig, recent.index[-1], recent.iloc[-1])  # Gold dot on today's value
    value_tag(fig, recent.iloc[-1], f"{recent.iloc[-1]:+.2f}", style.NAVY)  # Today's value as a tag
    value_tag(fig, median, f"{median:+.2f}", style.DARK_GREY)  # The median as a tag
    house_layout(fig, CARD_HEIGHT)                 # House look
    date_axes(fig)                                 # "Nov-26" dates
    return fig                                     # Hand back the figure


def figure_fixed_m1_m6(curves, prices, months=6):
    """Figure 3: today's M1 minus today's M6 contract, held fixed, over the past `months` months, for each market.

    curves -- dictionary of market -> (curve, date) from futures.curve_on()
    prices -- dictionary of market -> price table from futures.download_contracts()
    months -- how many months of history to show
    Returns the Plotly figure.
    """
    fig = go.Figure()                              # One panel
    fig.add_hline(y=0, line={"color": style.LIGHT_GREY, "width": 1})  # Zero line: above = backwardation, below = contango
    for market, (curve, date) in curves.items():   # "Brent" then "WTI"
        near, far = curve.index[0], curve.index[5] # Today's M1 and M6 contracts
        series = fixed_contract_spread(prices[market], near, far, date, months)  # Their daily spread over six months
        colour = style.MARKET_COLOURS[market]      # Navy for Brent, mid blue for WTI
        fig.add_trace(go.Scatter(x=series.index, y=series.values, name=market,  # One line per market...
                                 line={"color": colour, "width": 1.8},  # ...in its colour
                                 hovertemplate="%{y:+.2f}"))  # Hover shows the spread with a sign
        latest_dot(fig, series.index[-1], series.iloc[-1])  # Gold dot on its latest point
        value_tag(fig, series.iloc[-1], f"{series.iloc[-1]:+.2f}", colour)  # Its latest value as a tag
    house_layout(fig, CARD_HEIGHT)                 # House look
    date_axes(fig)                                 # "Jun-26" dates
    return fig                                     # Hand back the figure


def figure_wti_m1m2_histogram(curves, wti_history):
    """Figure 4: how many days in 2010-2024 had each WTI M1-M2 value, with today's value as a gold line.

    curves      -- dictionary of market -> (curve, date) from futures.curve_on() (only WTI is used)
    wti_history -- the table from eia.fetch_wti_futures_history()
    Returns the Plotly figure. Hover shows each bar's range and how many days fell in it.
    Uses the same edges and 50 bars as the static chart, so the two match (the lowest 0.5% of days are left off).
    """
    hist = wti_m1m2_history(wti_history)           # Daily WTI M1-M2, 2010 to April 2024
    today = time_spreads(curves["WTI"][0]).set_index("spread").loc["M1-M2", "value"]  # Today's WTI M1-M2
    lower = hist.quantile(0.005)                   # Left edge: the value only 0.5% of days fell below (as in charts.py)
    upper = max(hist.max(), today) + 0.25          # Right edge: the highest value plus a margin (as in charts.py)
    shown = hist[hist >= lower]                    # Leave off the extreme days below the left edge

    fig = go.Figure()                              # One panel
    fig.add_trace(go.Histogram(x=shown, name="Days",  # Count the days in each range...
                               xbins={"start": lower, "end": upper, "size": (upper - lower) / 50},  # ...50 equal ranges
                               marker={"color": style.MID_BLUE, "line": {"color": style.WHITE, "width": 0.5}},  # WTI blue, thin white gaps
                               hovertemplate="M1-M2 %{x}<br>%{y} days<extra></extra>"))  # Hover: the range and the count
    fig.add_vline(x=today, line={"color": style.GOLD, "width": 2},  # Today's value as a gold vertical line...
                  annotation_text=f"<b>Latest {today:+.2f}</b>", annotation_position="top right")  # ...labelled at the top
    house_layout(fig, CARD_HEIGHT)                 # House look
    fig.update_layout(hovermode="closest", showlegend=False, bargap=0)  # Hover one bar at a time; no key needed; bars touch
    fig.update_xaxes(title={"text": "WTI M1-M2 spread, $/bbl", "font": {"size": 11}})  # $/bbl runs along the bottom here
    return fig                                     # Hand back the figure


def figure_front_months(brent_front, wti_front, years=1):
    """Figure 5: Brent and WTI front-month futures over the past `years` years (top) and Brent minus WTI (bottom).

    brent_front -- the Series from futures.front_month_continuous("Brent")
    wti_front   -- the Series from futures.front_month_continuous("WTI")
    years       -- how many years back from the latest shared date to show
    Returns the Plotly figure. Zooming the top panel zooms the bottom one too, because they share their dates.
    """
    table = front_month_spread(brent_front, wti_front)  # brent, wti and spread columns, only on days both traded
    recent = table.loc[table.index.max() - pd.DateOffset(years=years):]  # Just the last year

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.06)  # Two panels, shared dates
    for market, column in [("Brent", "brent"), ("WTI", "wti")]:  # Each market's price line in the top panel
        colour = style.MARKET_COLOURS[market]      # Navy for Brent, mid blue for WTI
        fig.add_trace(go.Scatter(x=recent.index, y=recent[column], name=market,  # The front-month price...
                                 line={"color": colour, "width": 1.6},  # ...in the market's colour
                                 hovertemplate="%{y:.2f}"), row=1, col=1)  # Hover shows the price
        latest_dot(fig, recent.index[-1], recent[column].iloc[-1], row=1, col=1)  # Gold dot on its latest price
        value_tag(fig, recent[column].iloc[-1], f"{recent[column].iloc[-1]:.2f}", colour, yref="y")  # Its latest price as a tag
    fig.add_hline(y=0, line={"color": style.LIGHT_GREY, "width": 1}, row=2, col=1)  # Zero line in the bottom panel
    fig.add_trace(go.Scatter(x=recent.index, y=recent["spread"], name="Brent minus WTI",  # The gap between them...
                             line={"color": style.DARK_GREY, "width": 1.4},  # ...in grey (secondary series)
                             hovertemplate="%{y:+.2f}"), row=2, col=1)  # Hover shows it with a sign
    latest_dot(fig, recent.index[-1], recent["spread"].iloc[-1], row=2, col=1)  # Gold dot on today's gap
    value_tag(fig, recent["spread"].iloc[-1], f"{recent['spread'].iloc[-1]:+.2f}", style.DARK_GREY, yref="y2")  # Today's gap as a tag
    house_layout(fig, CARD_HEIGHT + 40)            # House look, a little taller to fit two panels
    date_axes(fig)                                 # "Nov-26" dates
    return fig                                     # Hand back the figure


def build_interactive(curves, prices, spot, wti_history, brent_front, wti_front):
    """Build all five interactive charts as pieces of HTML, ready to drop into the dashboard's cards.

    Inputs are the same tables that charts.save_all_charts() takes.
    Returns a dictionary of figure number -> HTML snippet (a <div> plus a little script that draws the chart).
    The Plotly JavaScript itself is NOT included in each snippet; the page loads it once with PLOTLY_SCRIPT.
    """
    figures = {                                    # Figure number -> Plotly figure, in the same order as charts.py
        1: figure_curves(curves, prices),          # Curves today vs a month earlier
        2: figure_brent_wti_spread(spot),          # Brent-WTI spot spread, two years
        3: figure_fixed_m1_m6(curves, prices),     # Fixed M1-M6 contracts, six months
        4: figure_wti_m1m2_histogram(curves, wti_history),  # WTI M1-M2 history
        5: figure_front_months(brent_front, wti_front),  # Brent vs WTI front months, one year
    }                                              # End of the figures
    return {number: fig.to_html(full_html=False, include_plotlyjs=False,  # Just the chart's <div>, not a whole page...
                                config=CONFIG, div_id=f"figure-{number}")  # ...with our settings and a fixed id
            for number, fig in figures.items()}    # One snippet per figure
