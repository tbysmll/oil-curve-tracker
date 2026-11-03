# Building the Oil Curve Tracker with Claude Code — a learning guide

The data layer (`eia.py`, `futures.py`) is already built and tested. You'll build the rest yourself in
Claude Code in VS Code, one step at a time. Each step teaches one Claude Code skill.

---

## Part 1 — Claude Code in five minutes

**What it is.** Claude Code is Claude working directly inside your project folder. Unlike the chat app,
it can read your files, write and edit code, and run commands in the terminal (with your permission).

**Opening it.** Open the project folder in VS Code (File > Open Folder). Click the **Spark icon**
(top-right of the editor when a file is open, or in the left sidebar). A chat panel opens.

**The five things to learn first:**

| Skill | How | Why it matters |
|---|---|---|
| **CLAUDE.md** | Already in this folder. Claude reads it at the start of every conversation. | Standing instructions, e.g. "annotate every line". Edit it any time you find yourself repeating an instruction. |
| **@-mentions** | Type `@` then a file name, e.g. `@futures.py`. Or select some lines and press `Alt+K` (Windows) / `Option+K` (Mac). | Points Claude at exactly the code you mean. |
| **Permission modes** | Click the mode indicator at the bottom of the prompt box. | **Manual**: Claude shows each edit as a side-by-side diff and waits for you to accept. **Plan**: Claude writes a plan and waits for approval before touching anything. **Use Manual and Plan while learning**, so you see every change. |
| **Plan first** | Switch to Plan mode, or type `/plan` followed by the task. | You review and comment on the approach before any code exists. Cheaper to fix a plan than a file. |
| **Undo** | Hover over any of your earlier messages and click the rewind button, then "Rewind code to here". Press `Esc` to stop Claude mid-task. | If Claude goes the wrong way, roll back instead of patching on top. |

**Good habits:**
- One step per conversation. Start a fresh one for each step below (Command Palette > "Claude Code: Open in New Tab"). Long conversations get muddled.
- Ask "why?" a lot. "Why did you use `ffill` there?" is a perfectly good prompt, and it's the point of the exercise.
- Run the code yourself after every step. Don't move on until you've seen it work.
- When something goes wrong, paste the full error message into Claude.

---

## Part 2 — Build it, step by step

Copy each prompt into Claude Code. They're written to be specific, and that's a skill too: notice how each one
says what to build, the exact definitions, and how to check it.

### Step 0 — Set up Python (learn: letting Claude run terminal commands)
> Set up this project for me: create a virtual environment in `.venv`, activate it and install `requirements.txt`. Explain each command before you run it, and tell me how to activate the environment myself next time.

Claude will ask permission before running each command. Read what it wants to run, then approve.

### Step 1 — Understand what's already built (learn: @-mentions, asking questions)
> Read @CLAUDE.md, @config.py, @eia.py and @futures.py. Explain in plain English how data flows through the project, then write and run a short test that prints today's Brent and WTI curves and the date each one comes from.

Then ask follow-ups until you can explain it yourself, e.g.:
> Why does `curve_on` sometimes use Friday's prices instead of today's?

### Step 2 — `spreads.py` (learn: Plan mode, reviewing a plan)
Switch to **Plan** mode first.
> Create `spreads.py` with functions that take the curves and price tables from @futures.py and @eia.py and calculate:
> 1. For each market: M1-M2, M1-M6 and M1-M12 spreads from today's curve.
> 2. A structure label for each spread: "backwardation", "contango" or "flat", using `NEUTRAL_BAND` from config.
> 3. The Brent-WTI spot spread from EIA.
> 4. Dated Brent (EIA spot) minus the Brent front-month future, on the latest date both exist.
> 5. Where today's WTI M1-M2 sits as a percentile of EIA's WTI M1-M2 history (2010 to April 2024).
> Follow the rules in CLAUDE.md. After building it, verify one spread by hand from the raw prices.

Read the plan. Comment on anything you don't understand **before** approving it.

### Step 3 — Check the numbers (learn: verifying Claude's work)
> Run spreads.py and show me every number it produces with its date. Then pick the Brent M1-M2 spread and the Brent-WTI spread and show the subtraction by hand from the raw prices.

Then check two spot prices yourself against EIA's page: https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm
Sanity check: on 30 Oct 2026 Brent M1 (Dec 26) was 117.64 and M2 (Jan 27) was 113.43, so M1-M2 should be +4.21 (backwardation).

### Step 4 — `charts.py` (learn: iterating on output you can see)
> Create `charts.py` that saves these PNG charts into `output/`:
> 1. Today's Brent and WTI curves (price by delivery month), each with the same contracts one month earlier as a dashed line.
> 2. The Brent-WTI spot spread over the past two years.
> 3. The spread between today's M1 and M6 contracts over the past six months (these two contracts held fixed), for Brent and WTI.
> 4. A histogram of WTI M1-M2 from EIA history with today's value marked.
> Label axes in $/bbl, put the data date in each title, and keep the style clean and simple.

Open the PNGs. If something looks off, say so in plain words ("the x-axis labels overlap", "make WTI orange").

### Step 5 — `main.py` (learn: tying a project together)
> Create `main.py` that runs the whole tracker: downloads the data, saves today's curve snapshots, calculates the spreads, makes the charts and writes `output/summary.md` with a table of today's numbers and their dates. Running `python main.py` should do everything.

### Step 6 — Weekly commentary with the Claude API (optional, like the gilt monitor)
> Add `commentary.py` that sends today's summary numbers to the Claude API and asks for a one-paragraph read of the oil curve, saved to `output/commentary.md`. Read the API key from `.env` as `ANTHROPIC_API_KEY`. Ask me before installing the `anthropic` library.

Note: the API is billed separately from your Claude subscription (a few pence per run). Always rewrite the draft yourself. Your own reading of the curve is what interviewers want to hear.

### Step 7 — Save your work to GitHub (learn: Git through Claude)
> Initialise a Git repository, make a first commit with a sensible message, and walk me through putting it on GitHub. Check that `.env` is NOT included before committing.

### Step 8 — Make it a habit
Run `python main.py` every few days. Each run adds a snapshot, so after a few weeks you'll have your own
history of the true rolling M1-M2 spread, which no free source gives you. Then ask Claude:
> Using `data/curve_snapshots.csv`, chart the rolling Brent and WTI M1-M2 spread over time.

---

## Part 3 — What you should be able to explain afterwards
- What backwardation and contango mean, and why storage costs limit how deep contango can go.
- Why Brent's curve is so steeply backwardated right now, and what that says about prompt supply.
- Why the Brent-WTI spread is so much wider than its usual few dollars.
- Why Dated Brent can trade far above front-month futures.
- Why you couldn't use EIA alone (futures data ended in 2024), and how you worked around Yahoo dropping expired contracts.

The last point makes a good interview story: you hit real data problems and solved them.
