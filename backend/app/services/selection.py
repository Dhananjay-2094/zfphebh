"""Select the latest forecast available by the day-ahead cutoff."""
import pandas as pd

from app.config import TIMEZONE


def cutoff_times(start_time: pd.Series, cutoff_hour: float) -> pd.Series:
    """Return each delivery half-hour's cutoff as a UTC timestamp."""
    # Calculate each delivery period’s day-ahead cutoff as a UTC timestamp.
    local_day = start_time.dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()
    naive = local_day - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    local = naive.dt.tz_localize(TIMEZONE, ambiguous="NaT", nonexistent="shift_forward")
    return local.dt.tz_convert("UTC")


def decision_forecast(forecast: pd.DataFrame, cutoff_hour: float) -> pd.DataFrame:
    """Keep the latest eligible publication for each delivery half-hour."""
    # Select the newest forecast publication available by cutoff per delivery period.
    f = forecast.copy()
    f["cutoff_time"] = cutoff_times(f["start_time"], cutoff_hour)
    f = f[f["publish_time"] <= f["cutoff_time"]]
    f = (f.sort_values(["start_time", "publish_time"])
          .groupby("start_time", as_index=False).tail(1))
    f["horizon_h"] = (f["start_time"] - f["publish_time"]).dt.total_seconds() / 3600
    f = f.rename(columns={"generation_mw": "forecast_mw"})
    return f.reset_index(drop=True)
