"""Forecast error metrics. error = forecast - actual (positive = forecast too high)."""
import numpy as np
import pandas as pd

from app.config import TIMEZONE

HORIZON_BINS = [0, 6, 12, 24, 36, 48, 72.001]
HORIZON_LABELS = ["0-6h", "6-12h", "12-24h", "24-36h", "36-48h", "48-72h"]


def join_actuals(forecast: pd.DataFrame, actual: pd.DataFrame) -> pd.DataFrame:
    """Join matching delivery periods and calculate forecast errors."""
    df = forecast.merge(actual, on="start_time", how="inner")
    df["error"] = df["forecast_mw"] - df["actual_mw"]
    df["abs_error"] = df["error"].abs()
    df["sq_error"] = df["error"] ** 2
    local = df["start_time"].dt.tz_convert(TIMEZONE)
    df["day"] = local.dt.tz_localize(None).dt.normalize()  # UK-local delivery day
    df["hour"] = local.dt.hour
    return df


def in_range(df: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    m = pd.Series(True, index=df.index)
    if start is not None:
        m &= df["day"] >= pd.Timestamp(start)
    if end is not None:
        m &= df["day"] <= pd.Timestamp(end)
    return df[m]


def _r(x, nd=1):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0, "mae_mw": None, "rmse_mw": None, "bias_mw": None,
                "nmae_pct": None, "mean_actual_mw": None,
                "error_p10_mw": None, "error_p50_mw": None, "error_p90_mw": None}
    mean_actual = df["actual_mw"].mean()
    mae = df["abs_error"].mean()
    p10, p50, p90 = df["error"].quantile([0.1, 0.5, 0.9])
    return {
        "n": int(len(df)),
        "mae_mw": _r(mae),
        "rmse_mw": _r(np.sqrt(df["sq_error"].mean())),
        "bias_mw": _r(df["error"].mean()),
        "nmae_pct": _r(100 * mae / mean_actual) if mean_actual else None,
        "mean_actual_mw": _r(mean_actual),
        "error_p10_mw": _r(p10), "error_p50_mw": _r(p50), "error_p90_mw": _r(p90),
    }


def _group_rows(df, key, labels):
    g = df.groupby(key, observed=True)
    out = g.agg(n=("error", "size"), mae=("abs_error", "mean"),
                mse=("sq_error", "mean"), bias=("error", "mean")).reset_index()
    rows = []
    for _, r in out.iterrows():
        rows.append({"key": labels(r[key]), "n": int(r["n"]), "mae_mw": _r(r["mae"]),
                     "rmse_mw": _r(np.sqrt(r["mse"])), "bias_mw": _r(r["bias"])})
    return rows


def breakdown(by: str, decision_eval: pd.DataFrame, all_eval: pd.DataFrame) -> list[dict]:
    """Error metrics sliced by hour, lead time (horizon), day or forecast level.

    hour / day / wind_level use the decision-time forecast (what the buyer had).
    horizon uses every published forecast, to show how accuracy decays with lead time.
    """
    if by == "hour":
        return _group_rows(decision_eval, "hour", lambda h: f"{int(h):02d}:00")
    if by == "day":
        return _group_rows(decision_eval, "day", lambda d: d.strftime("%d %b"))
    if by == "horizon":
        df = all_eval.copy()
        df["bin"] = pd.cut(df["horizon_h"], HORIZON_BINS, labels=HORIZON_LABELS, right=True,
                           include_lowest=True)
        return _group_rows(df.dropna(subset=["bin"]), "bin", str)
    if by == "wind_level":
        if decision_eval["forecast_mw"].nunique() < 3:
            return []
        q = pd.qcut(decision_eval["forecast_mw"], 3, labels=["Low", "Medium", "High"],
                    duplicates="drop")
        df = decision_eval.assign(level=q)
        return _group_rows(df, "level", lambda s: f"{s} forecast")
    raise ValueError(f"unknown breakdown: {by}")


def distribution(df: pd.DataFrame, bins: int = 24) -> dict:
    if df.empty:
        return {"bins": [], "p10_mw": None, "p50_mw": None, "p90_mw": None}
    counts, edges = np.histogram(df["error"], bins=bins)
    p10, p50, p90 = df["error"].quantile([0.1, 0.5, 0.9])
    return {
        "bins": [{"lo": _r(edges[i]), "hi": _r(edges[i + 1]),
                  "mid": _r((edges[i] + edges[i + 1]) / 2), "count": int(counts[i])}
                 for i in range(len(counts))],
        "p10_mw": _r(p10), "p50_mw": _r(p50), "p90_mw": _r(p90),
    }
