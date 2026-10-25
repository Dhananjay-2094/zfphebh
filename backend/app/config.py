"""Central settings and default dashboard window."""
import os
from datetime import date

DEFAULT_START_DAY = date(2026, 1, 1)
DEFAULT_END_DAY = date(2026, 1, 31)
DEFAULT_DELIVERY_DAY = date(2026, 1, 14)
TIMEZONE = "Europe/London"
DEFAULT_CUTOFF_HOUR = 9.0
MIN_PRIOR_DAYS = 3
MAX_RANGE_DAYS = 366
BANDS = {
    "p05_p95": (0.05, 0.95, "Wide (90% of past errors)"),
    "p10_p90": (0.10, 0.90, "Standard (80% of past errors)"),
    "p25_p75": (0.25, 0.75, "Narrow (50% of past errors)"),
}
DEFAULT_BAND = "p10_p90"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
