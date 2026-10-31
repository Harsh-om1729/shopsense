"""Shared project paths and constants."""

from pathlib import Path

# Resolved from this file, so paths work from notebooks/, tests/, or the root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Pass this to every split, CV, and model so runs stay comparable.
RANDOM_SEED = 42
