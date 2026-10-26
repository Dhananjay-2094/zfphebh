"""Ready-to-query frames derived from an Elexon date range."""
from datetime import date

from app.data import get_dataset
from app.services import metrics, selection


def norm_cutoff(hour: float) -> float:
    # Round a cutoff hour to the nearest half-hour increment.
    return round(float(hour) * 2) / 2


def dataset(start: date, end: date):
    # Retrieve actual and forecast data for a date range.
    return get_dataset(start, end)


def decision(start: date, end: date, cutoff_hour: float):
    # Build the delivery-day forecast response and summary statistics.
    data = dataset(start, end)
    return selection.decision_forecast(data.forecast, cutoff_hour)


def evaluation(start: date, end: date, cutoff_hour: float):
    # Join cutoff-selected forecasts to actuals and restrict them to the date range.
    data = dataset(start, end)
    forecasts = selection.decision_forecast(data.forecast, cutoff_hour)
    return metrics.in_range(metrics.join_actuals(forecasts, data.actual), start, end)


def evaluation_all_horizons(start: date, end: date):
    # Evaluate every published forecast against actuals with its lead time.
    data = dataset(start, end)
    forecasts = data.forecast.rename(columns={"generation_mw": "forecast_mw"}).copy()
    forecasts["horizon_h"] = (
        forecasts["start_time"] - forecasts["publish_time"]
    ).dt.total_seconds() / 3600
    evaluated = metrics.join_actuals(forecasts, data.actual)
    return metrics.in_range(evaluated, start, end)
