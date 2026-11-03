# Oil Curve Tracker — instructions for Claude Code

Claude Code reads this file at the start of every conversation in this folder.
Anything written here applies to every task, so I don't have to repeat it.

## Who I am and why this project exists
- I'm Toby, a final-year Economics student at Bath, building this to learn oil markets AND to learn Claude Code.
- I know some Python (CS50, pandas basics) but I'm not a developer. Treat me as a learner.
- The project goes on my CV ("Oil Curve Tracker"), so I must be able to explain every line and every number in an interview.

## Coding rules (always follow these)
1. **Annotate every line of code.** Every line gets a plain-English comment saying what it does and why,
   either at the end of the line or on the line above. No exceptions, including imports and short lines.
   Every function also gets a docstring explaining its inputs, what it returns, and why it exists.
   Match the commenting style already used in `eia.py` and `futures.py`.
2. **Keep it simple.** Prefer clear pandas over clever one-liners. No new libraries without asking me first.
3. **Small steps.** Build one file or one function at a time, then stop so I can review and run it.
4. **Explain before and after.** Before writing code, tell me in a few sentences what you'll do. After, tell me
   how to run it and what output I should expect to see.
5. **Teach the finance too.** When code calculates something (a spread, a percentile), explain in one or
   two sentences what it means for the oil market.
6. **Never print, log or hard-code the API key.** It lives in `.env`, which Git ignores.

## How the project is structured
- `config.py` — all settings (folders, number of contracts, start dates, the "flat" band, the freshness limit, URLs). Change settings here only.
- `eia.py` — official EIA data: Brent and WTI **spot** prices (current), and WTI futures contracts 1-4 (history only).
- `futures.py` — today's Brent and WTI **futures curves** from Yahoo Finance, the continuous front-month series, and the daily snapshot store.
- `spreads.py` — every calculation (time spreads and labels, Brent-WTI, Dated Brent vs future, percentile, histories). No downloads.
- `chart_style.py` — the house style for every chart and the web page: palette, font, size, layout and labelling helpers.
- `charts.py` — draws the five static SVG charts into `docs/charts/` (README, and the website's fallback). Drawing only.
- `interactive.py` — the website's interactive Plotly versions of the same five charts (hover, drag to zoom).
- `report.py` — builds the numbers table once, then the Markdown summary and the web page `docs/index.html`.
- `main.py` — runs everything: download, check, calculate, chart, write reports, and only then save the snapshot.
- `commentary.txt` — my own commentary, shown on the web page.
- `test_curves.py` — quick check that both curves download and build.
- `.github/workflows/daily-update.yml` — runs `main.py` on GitHub every weekday and commits the results.

## How it runs
- **Locally:** activate `.venv`, then `python main.py`. It writes `data/curve_snapshots.csv`, `output/summary.md`,
  `docs/charts/*.svg`, `docs/index.html` and the README's "Latest numbers" section.
- **On GitHub:** the workflow runs at 22:30 UK time on weekdays (two cron lines, 21:30 and 22:30 UTC, plus a check of the
  UK clock, because GitHub's timetable only understands UTC). It reads the EIA key from the repository secret `EIA_API_KEY`
  and commits the outputs as `github-actions[bot]`. It can also be run by hand: Actions → Daily curve update → Run workflow.
- **Website:** GitHub Pages publishes the `docs/` folder at https://tbysmll.github.io/oil-curve-tracker/
- **Before I push anything:** `git pull --rebase` first, because the bot commits every weekday night.
- If `main.py` runs during US trading hours, the snapshot holds live prices; that night's run replaces them with the close.
- Any failed download or check stops the run **before anything is saved**, so the workflow never commits bad data. Keep it that way.
- The workflow checks out `ref: main` and uses `git pull --rebase -X theirs`, so overlapping runs (or a push during a run) don't
  fail on conflicts in the generated files. Safe because the bot only ever commits generated files. Don't remove either.

## Charts and the web page
- All styling lives in `chart_style.py`. Use only its palette: navy #002B5C (Brent / main series), mid blue #4F81BD (WTI),
  gold #C9A227 (today's value), dark grey #595959 (text, secondary series), light grey #D9D9D9 (gridlines), on white.
- Charts are **card charts**: the image is only the plot, drawn inside `plt.rc_context(style.rc_params())` at `CARD_SIZE`
  (half-width) or `WIDE_SIZE` (Figure 1), saved as **SVG** (`FILE_TYPE`) so they stay sharp at any size; clicking one on the
  dashboard opens it full size. Lettering is saved as shapes and the files carry no date or random IDs, so unchanged charts don't change in Git. Plot style: y-axis numbers on the right, bottom baseline only, small unboxed
  key above the plot, each line's latest value in a coloured tag on the right axis (`value_tag`, with `hide_numbers_under_tags`),
  and a gold dot on the latest point.
- Each plot function returns `chart_info(...)`: file, figure number, a takeaway title **generated from the data** (using
  `NEUTRAL_BAND` for "up"/"down"/"little changed"), subtitle (what's plotted and the units), source line with the data date(s),
  and any note. `report.py` puts these in the dashboard card around the image, and as text around it in the README.
- The web page is a dashboard: navy masthead, six headline tiles (`headline_tiles`; day-on-day changes compare the SAME
  contract, never across a roll), Figure 1 full width, Figures 2-5 in pairs, a commentary sidebar, and the full numbers table.
- Charts are saved once, in `docs/charts/`; the README, `output/summary.md` and the web page all link to the same files.
- The web page's CSS takes its colours from `chart_style.py`, so the page and the charts always match.
- On the website the charts are interactive (Plotly, approved by me): `interactive.py` uses the same `spreads.py` numbers and
  house style; the card text still comes from `charts.py`; Plotly's JavaScript loads from cdn.plot.ly, pinned to the installed
  version; each card links to its static SVG, which also shows if JavaScript is blocked. Each headline tile has a plain-English
  explanation that changes with the data (`slope_meaning`, `percentile_meaning`, `physical_meaning`).
- The README text between `<!-- LATEST-NUMBERS:START -->` and `<!-- LATEST-NUMBERS:END -->` is rewritten on every run. Don't edit it by hand.

## Commentary
- `commentary.txt` is **my own words**. Claude may draft commentary in the chat for me to learn from, but never writes into this file.
- A Claude routine ("Monday oil commentary draft") drafts it every Monday at 08:00 UK time from the public repo; I rewrite it myself.
- Commentary must describe only what the numbers show, with a date next to every number. No invented news or causes.

## Data facts learned the hard way (don't "fix" these)
- EIA's futures series (RCLC1-4) **stopped updating on 5 April 2024**. Use them for long-run history only.
- EIA spot prices are published a few days behind (daily values released in weekly batches).
- Yahoo **deletes contracts once they expire**, so past rolling M1-M2 spreads can't be rebuilt from Yahoo.
  That's why `futures.save_snapshot()` stores each day's curve in `data/curve_snapshots.csv`.
- During trading hours Yahoo's latest row is live prices, and thin back-month contracts may not have traded yet.
  `futures.curve_on()` therefore uses the most recent day where all 12 contracts have a price.
  This means the Brent and WTI curves can come from different dates — always show the date next to any number.
- Brent futures stop trading about two months before delivery (e.g. the Jan 2027 contract expires end of Nov 2026).
- Yahoo's continuous front-month series (BZ=F, CL=F) jumps on roll days. Don't treat those jumps as price moves.
- **Combining sources:** any calculation that combines two data sources must use the latest date that BOTH sources have,
  never each source's own latest date (e.g. Dated Brent minus the front-month future). Calculations within one source
  (a curve's own spreads, Brent-WTI spot from EIA) can use that source's latest date. Every number in the output must
  show the date it's from. Exception: today's WTI M1-M2 is deliberately compared with the 2010-2024 EIA history.
- Yahoo contracts are downloaded **one at a time** (`threads=False`). Parallel downloads clash over yfinance's cache
  ("database is locked") and silently lose a contract, which would shift every spread. `check_consecutive()` is the safety net.
- The two continuous front-month series are usually **different delivery months**: Brent's front month is about one month
  further out than WTI's (e.g. on 2 Nov 2026, BZ=F was Jan-27 and CL=F was Dec-26). So their gap isn't a same-month comparison.
- `requests`' own error messages include the full web address, **which contains the API key**. `eia.py` checks replies itself
  and raises its own errors; never go back to `raise_for_status()`.
- Matplotlib reads text between two `$` signs as a maths formula, which garbles "$/bbl ... $/bbl". The house style turns
  this off (`text.parse_math: False`).

## Definitions used in this project
- **M1, M2 ... M12**: the 1st, 2nd ... 12th contracts along the curve, nearest delivery first.
- **Time spread** = nearer contract minus further contract (e.g. M1-M2). Positive = backwardation, negative = contango.
- **Flat**: a spread within ±`NEUTRAL_BAND` ($0.10) of zero.
- **Brent-WTI spread** = Brent spot minus WTI spot (EIA).

## Checking the work
- After any calculation, verify at least one number by hand from the raw prices and show me the working.
- Compare spot prices against EIA's published page: https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm
