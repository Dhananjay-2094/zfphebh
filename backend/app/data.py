"""Fetch and cache requested national wind data from Elexon."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from threading import Lock
import time
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
CACHE_TTL_SECONDS = 300
CACHE_MAX_ENTRIES = 32
_EMPTY_ACTUAL = {"start_time": "datetime64[ns, UTC]", "actual_mw": "float64"}
_EMPTY_FORECAST = {
    "start_time": "datetime64[ns, UTC]",
    "publish_time": "datetime64[ns, UTC]",
    "generation_mw": "float64",
}
_cache = {}
_cache_lock = Lock()


class ElexonUnavailable(RuntimeError):
    """Raised when an Elexon request cannot be completed."""


@dataclass(frozen=True)
class Dataset:
    actual: pd.DataFrame
    forecast: pd.DataFrame


def _empty_frame(columns: dict) -> pd.DataFrame:
    # Build an empty DataFrame with the requested column names and dtypes.
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in columns.items()})


def _request(dataset: str, params: dict) -> list:
    # Fetch one Elexon dataset endpoint and normalize its response into a list of records.
    try:
        response = httpx.get(f"{BASE_URL}/{dataset}/stream", params=params,
                             headers={"accept": "application/json"}, timeout=45)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ElexonUnavailable(f"Elexon {dataset} request failed: {exc}") from exc
    return body.get("data", []) if isinstance(body, dict) else body


def _utc_bounds(start: date, end: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    # Convert an inclusive London-local date range into UTC half-open timestamp bounds.
    lo = pd.Timestamp(start).tz_localize("Europe/London").tz_convert("UTC")
    hi = pd.Timestamp(end + timedelta(days=1)).tz_localize("Europe/London").tz_convert("UTC")
    return lo, hi


def _windows(start: date, end: date, step_days: int):
    # Yield consecutive date windows no longer than the requested number of days.
    current = start
    while current <= end:
        last = min(current + timedelta(days=step_days - 1), end)
        yield current, last
        current = last + timedelta(days=1)


def _actual(start: date, end: date) -> pd.DataFrame:
    # Load and clean actual national wind generation for the requested dates.
    actual_end = min(end, datetime.now(ZoneInfo("Europe/London")).date())
    if start > actual_end:
        return _empty_frame(_EMPTY_ACTUAL)

    rows = []
    for first, last in _windows(start, actual_end, 7):
        rows.extend(_request("FUELHH", {
            "settlementDateFrom": first.isoformat(),
            "settlementDateTo": (last + timedelta(days=1)).isoformat(),
            "fuelType": "WIND",
        }))
    if not rows:
        return _empty_frame(_EMPTY_ACTUAL)

    raw = pd.DataFrame(rows)
    raw = raw[raw["fuelType"].eq("WIND")].copy()
    if raw.empty:
        return _empty_frame(_EMPTY_ACTUAL)
    if "publishTime" in raw:
        raw = raw.sort_values("publishTime")
    raw["start_time"] = pd.to_datetime(raw["startTime"], utc=True)
    raw = raw.drop_duplicates("start_time", keep="last")
    actual = pd.DataFrame({
        "start_time": raw["start_time"],
        "actual_mw": pd.to_numeric(raw["generation"], errors="coerce"),
    }).dropna()
    lo, hi = _utc_bounds(start, actual_end)
    return (actual[(actual.start_time >= lo) & (actual.start_time < hi)]
            .sort_values("start_time").reset_index(drop=True))


def _forecast(start: date, end: date) -> pd.DataFrame:
    # Load forecast publications and retain usable delivery-time and lead-time records.
    rows = []
    # Earlier publications are needed to reconstruct the day-ahead cutoff forecast.
    for first, last in _windows(start - timedelta(days=4), end, 2):
        rows.extend(_request("WINDFOR", {
            "publishDateTimeFrom": f"{first.isoformat()}T00:00:00Z",
            "publishDateTimeTo": f"{(last + timedelta(days=1)).isoformat()}T00:00:00Z",
        }))
    if not rows:
        return _empty_frame(_EMPTY_FORECAST)

    raw = pd.DataFrame(rows)
    forecast = pd.DataFrame({
        "start_time": pd.to_datetime(raw["startTime"], utc=True),
        "publish_time": pd.to_datetime(raw["publishTime"], utc=True),
        "generation_mw": pd.to_numeric(raw["generation"], errors="coerce"),
    }).dropna()
    horizon = (forecast.start_time - forecast.publish_time).dt.total_seconds() / 3600
    lo, hi = _utc_bounds(start, end)
    forecast = forecast[(horizon > 0) & (horizon <= 72)
                        & (forecast.start_time >= lo) & (forecast.start_time < hi)]
    return (forecast.drop_duplicates(["start_time", "publish_time"], keep="last")
            .sort_values(["start_time", "publish_time"]).reset_index(drop=True))


def get_dataset(start: date, end: date) -> Dataset:
    # Return cached actual and forecast frames, fetching and caching them when needed.
    key = (start.isoformat(), end.isoformat())
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    dataset = Dataset(actual=_actual(start, end), forecast=_forecast(start, end))
    with _cache_lock:
        _cache[key] = (time.monotonic(), dataset)
        if len(_cache) > CACHE_MAX_ENTRIES:
            oldest = min(_cache, key=lambda item: _cache[item][0])
            del _cache[oldest]
    return dataset
