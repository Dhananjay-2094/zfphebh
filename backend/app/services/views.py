"""Builds the JSON-ready payloads for each endpoint."""
from datetime import date

import pandas as pd

from app.config import (
    BANDS, DEFAULT_BAND, DEFAULT_CUTOFF_HOUR, DEFAULT_DELIVERY_DAY,
    DEFAULT_END_DAY, DEFAULT_START_DAY, MAX_RANGE_DAYS, TIMEZONE,
)
from app.data import ElexonUnavailable
from app.services import metrics, shortfall, store


class NotFound(Exception):
    pass


class UpstreamError(RuntimeError):
    pass


def _num(x, nd=1):
    # Round a numeric value for JSON output while mapping missing values to None.
    return None if x is None or pd.isna(x) else round(float(x), nd)


def _check_range(start: date, end: date):
    # Validate date ordering and enforce the configured maximum range length.
    if start > end:
        raise NotFound("start_date must be on or before end_date")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise NotFound(f"date range cannot exceed {MAX_RANGE_DAYS} days")
    return start, end


def _check_day(d: date, start: date, end: date):
    # Validate a delivery date against its range and return it as a pandas timestamp.
    _check_range(start, end)
    if not start <= d <= end:
        raise NotFound("delivery_date must be within the selected date range")
    return pd.Timestamp(d)


def _safe(fn, *args):
    # Convert upstream Elexon fetch failures into the service-layer exception type.
    try:
        return fn(*args)
    except ElexonUnavailable as exc:
        raise UpstreamError(str(exc)) from exc


def _local_day(df: pd.DataFrame) -> pd.Series:
    # Convert UTC delivery timestamps to normalized local calendar dates.
    return df["start_time"].dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()


def meta() -> dict:
    # Return API defaults, supported bands, timezone, and error sign convention.
    return {
        "source": "elexon",
        "default_start_day": DEFAULT_START_DAY.isoformat(),
        "default_end_day": DEFAULT_END_DAY.isoformat(),
        "default_delivery_day": DEFAULT_DELIVERY_DAY.isoformat(),
        "default_cutoff_hour": DEFAULT_CUTOFF_HOUR,
        "timezone": TIMEZONE,
        "max_range_days": MAX_RANGE_DAYS,
        "default_band": DEFAULT_BAND,
        "bands": [{"key": k, "label": v[2], "coverage_pct": round(100 * (v[1] - v[0]))}
                  for k, v in BANDS.items()],
        "sign_convention": "error = forecast - actual; positive means the forecast was too high",
    }


def decision(
    delivery_date: date, cutoff_hour: float, start: date | None = None, end: date | None = None,
):
    # Build the delivery-day forecast response and summary statistics.
    start = start or delivery_date
    end = end or delivery_date
    day = _check_day(delivery_date, start, end)
    c = store.norm_cutoff(cutoff_hour)
    d = _safe(store.decision, start, end, c)
    rows = d[_local_day(d) == day]
    if rows.empty:
        raise NotFound(f"no forecast published before the cutoff for {delivery_date}")
    actual = _safe(store.dataset, start, end).actual
    rows = rows.merge(actual, on="start_time", how="left").sort_values("start_time")
    peak, low = rows.loc[rows["forecast_mw"].idxmax()], rows.loc[rows["forecast_mw"].idxmin()]
    return {
        "delivery_date": str(delivery_date), "cutoff_hour": c,
        "summary": {
            "cutoff_time": rows["cutoff_time"].iloc[0].isoformat(),
            "avg_mw": _num(rows["forecast_mw"].mean()),
            "peak_mw": _num(peak["forecast_mw"]), "peak_time": peak["start_time"].isoformat(),
            "low_mw": _num(low["forecast_mw"]), "low_time": low["start_time"].isoformat(),
            "first_publish": rows["publish_time"].min().isoformat(),
            "last_publish": rows["publish_time"].max().isoformat(), "n_points": int(len(rows)),
        },
        "points": [{"start_time": r.start_time.isoformat(), "publish_time": r.publish_time.isoformat(),
                    "forecast_mw": _num(r.forecast_mw), "actual_mw": _num(r.actual_mw)}
                   for r in rows.itertuples()],
    }


def _eval(start, end, cutoff_hour):
    # Validate a range, normalize the cutoff, and load evaluated forecast rows.
    _check_range(start, end)
    c = store.norm_cutoff(cutoff_hour)
    return c, _safe(store.evaluation, start, end, c)


def accuracy_summary(start, end, cutoff_hour: float):
    # Build the aggregate accuracy response for a selected range and cutoff.
    c, ev = _eval(start, end, cutoff_hour)
    return {"cutoff_hour": c, "start": str(start), "end": str(end), **metrics.summarize(ev)}


def accuracy_breakdown(by: str, start, end, cutoff_hour: float):
    # Build grouped accuracy output, translating invalid grouping requests.
    c, ev = _eval(start, end, cutoff_hour)
    allv = _safe(store.evaluation_all_horizons, start, end)
    try:
        rows = metrics.breakdown(by, ev, allv)
    except ValueError as exc:
        raise NotFound(str(exc)) from exc
    return {"by": by, "cutoff_hour": c, "rows": rows}


def accuracy_distribution(start, end, cutoff_hour: float):
    # Build the error distribution response for a selected range and cutoff.
    c, ev = _eval(start, end, cutoff_hour)
    return {"cutoff_hour": c, **metrics.distribution(ev)}


def shortfall_view(
    delivery_date: date, start: date, end: date, demand_mw: float, band: str, cutoff_hour: float,
):
    # Validate inputs and produce procurement shortfall estimates for one day.
    day = _check_day(delivery_date, start, end)
    if band not in BANDS:
        raise NotFound(f"band must be one of {list(BANDS)}")
    c = store.norm_cutoff(cutoff_hour)
    d = _safe(store.decision, start, end, c)
    day_fc = d[_local_day(d) == day]
    if day_fc.empty:
        raise NotFound(f"no forecast published before the cutoff for {delivery_date}")
    ev = _safe(store.evaluation, start, end, c)
    out = shortfall.compute(day_fc, ev, day, demand_mw, band)
    return {"delivery_date": str(delivery_date), "cutoff_hour": c, **out}
