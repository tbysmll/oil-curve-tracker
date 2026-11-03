"""
config.py - every setting the tracker uses, kept in one place.

If you want to change how many contracts are pulled, how far back the history
goes, or where files are saved, this is the only file you need to edit.
"""

from pathlib import Path          # Path builds file paths that work on both Windows and Mac
import os                         # os lets Python read "environment variables" (where the key ends up)
from dotenv import load_dotenv    # load_dotenv reads the .env file and turns its lines into environment variables

load_dotenv()                     # Run it now, so EIA_API_KEY from the .env file is available below

# ---------------------------------------------------------------------------
# EIA (U.S. Energy Information Administration) API settings
# ---------------------------------------------------------------------------
EIA_API_KEY = os.getenv("EIA_API_KEY")    # Read the key from the environment; this is None if .env is missing
EIA_BASE_URL = "https://api.eia.gov/v2"   # The root web address of EIA's API (version 2)

# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent   # The folder this file sits in, i.e. the project folder
DATA_DIR = BASE_DIR / "data"                 # Downloaded data and the saved daily curve snapshots go here
OUTPUT_DIR = BASE_DIR / "output"             # Charts and the written summary go here
DATA_DIR.mkdir(exist_ok=True)                # Create the data folder if it isn't there yet (no error if it is)
OUTPUT_DIR.mkdir(exist_ok=True)              # Same for the output folder

# ---------------------------------------------------------------------------
# Futures contract settings
# ---------------------------------------------------------------------------
# Exchanges name each delivery month with a letter code:
# F=Jan G=Feb H=Mar J=Apr K=May M=Jun N=Jul Q=Aug U=Sep V=Oct X=Nov Z=Dec
MONTH_CODES = "FGHJKMNQUVXZ"      # Position 0 is January, position 11 is December

# The two markets we track. "root" is the start of each contract's ticker on Yahoo Finance,
# e.g. Brent January 2027 is "BZ" + "F" + "27" + ".NYM" = BZF27.NYM
MARKETS = {
    "Brent": {"root": "BZ", "exchange": "NYM", "colour": "#1f4e79"},  # NYMEX Brent Last Day Financial; settles against ICE Brent
    "WTI":   {"root": "CL", "exchange": "NYM", "colour": "#c55a11"},  # NYMEX WTI Light Sweet Crude, delivered at Cushing, Oklahoma
}

CURVE_MONTHS = 12            # How many contracts along the curve to track: M1 (front month) out to M12
HISTORY_START = "2025-01-01" # How far back to download each live contract's price history
LONG_RUN_START = "2010-01-01"  # Start of the EIA history used to judge whether today's spreads are unusual

# A spread this close to zero (in $/bbl) is called "flat" rather than backwardation or contango.
# Without this buffer the label would flicker back and forth on days when the spread is near zero.
NEUTRAL_BAND = 0.10

# If the newest complete curve Yahoo gives us is older than this many days, stop instead of saving it.
# 5 days covers a weekend plus a market holiday; anything older means Yahoo has stopped updating.
STALE_AFTER_DAYS = 5
