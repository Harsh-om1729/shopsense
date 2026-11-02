"""Shared project paths and constants."""

from pathlib import Path

# Resolved from this file, so paths work from notebooks/, tests/, or the root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
OLIST_DIR = DATA_RAW_DIR / "olist"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FEATURES_DIR = DATA_PROCESSED_DIR / "features"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Pass this to every split, CV, and model so runs stay comparable.
RANDOM_SEED = 42

# First and last order dates used. Orders fade out after the last date,
# which looks like an extraction cut-off rather than real demand.
FIRST_ORDER_DATE = "2017-01-01"
LAST_ORDER_DATE = "2018-08-21"

# Orders purchased on or after this date are the final test period.
# Study feature and target relationships on earlier orders only.
HOLDOUT_START = "2018-06-01"

# Rows this close to the holdout are excluded from training, because their
# outcomes may not be known yet. Dropping only unfinished orders would remove
# slow deliveries and bias the training data.
EMBARGO_DAYS = 30
