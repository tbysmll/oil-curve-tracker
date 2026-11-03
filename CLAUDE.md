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
- `config.py` — all settings (folders, number of contracts, start dates, the "flat" band). Change settings here only.
- `eia.py` — official EIA data: Brent and WTI **spot** prices (current), and WTI futures contracts 1-4 (history only).
- `futures.py` — today's Brent and WTI **futures curves** from Yahoo Finance, plus a daily snapshot store.
- To build: `spreads.py` (calculations), `charts.py` (charts), `main.py` (runs everything, writes `output/`).

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

## Definitions used in this project
- **M1, M2 ... M12**: the 1st, 2nd ... 12th contracts along the curve, nearest delivery first.
- **Time spread** = nearer contract minus further contract (e.g. M1-M2). Positive = backwardation, negative = contango.
- **Flat**: a spread within ±`NEUTRAL_BAND` ($0.10) of zero.
- **Brent-WTI spread** = Brent spot minus WTI spot (EIA).

## Checking the work
- After any calculation, verify at least one number by hand from the raw prices and show me the working.
- Compare spot prices against EIA's published page: https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm
