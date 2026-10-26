"""Estimate a procurement range from forecast errors."""
import pandas as pd

from app.config import BANDS, MIN_PRIOR_DAYS


def band_errors(eval_df: pd.DataFrame, delivery_day: pd.Timestamp, lo_q: float, hi_q: float):
    """Use prior-day errors when enough history is available."""
    # Choose calibration errors from prior days when enough history exists.
    prior = eval_df[eval_df["day"] < delivery_day]
    n_days = prior["day"].nunique()
    if n_days >= MIN_PRIOR_DAYS:
        src, method = prior, "walk_forward"
    else:
        src, method = eval_df, "in_sample"
        n_days = src["day"].nunique()
    if src.empty:
        return 0.0, 0.0, {"method": "none", "days_used": 0}
    e_lo, e_hi = src["error"].quantile([lo_q, hi_q])
    return float(e_lo), float(e_hi), {"method": method, "days_used": int(n_days)}


def walk_forward_coverage(eval_df: pd.DataFrame, lo_q: float, hi_q: float) -> dict:
    """Measure coverage using bands fitted only on earlier days."""
    # Measure interval coverage by testing each day against earlier-day errors.
    inside = total = 0
    for day in sorted(eval_df["day"].unique()):
        prior = eval_df[eval_df["day"] < day]
        if prior["day"].nunique() < MIN_PRIOR_DAYS:
            continue
        e_lo, e_hi = prior["error"].quantile([lo_q, hi_q])
        errs = eval_df.loc[eval_df["day"] == day, "error"]
        inside += int(((errs >= e_lo) & (errs <= e_hi)).sum())
        total += len(errs)
    return {"coverage_pct": round(100 * inside / total, 1) if total else None,
            "target_pct": round(100 * (hi_q - lo_q), 1), "n": total}


def compute(day_forecast: pd.DataFrame, eval_df: pd.DataFrame, delivery_day: pd.Timestamp,
            demand_mw: float, band: str) -> dict:
    # Estimate wind and procurement ranges, summaries, and backtested coverage.
    lo_q, hi_q, label = BANDS[band]
    e_lo, e_hi, info = band_errors(eval_df, delivery_day, lo_q, hi_q)

    df = day_forecast.sort_values("start_time").copy()
    df["wind_low"] = (df["forecast_mw"] - e_hi).clip(lower=0)
    df["wind_high"] = (df["forecast_mw"] - e_lo).clip(lower=0)
    df["buy_min"] = (demand_mw - df["wind_high"]).clip(lower=0)
    df["buy_max"] = (demand_mw - df["wind_low"]).clip(lower=0)
    df["buy_mid"] = (demand_mw - df["forecast_mw"]).clip(lower=0)

    steps = df["start_time"].diff().dropna()
    step_h = float(steps.mode().iloc[0].total_seconds() / 3600) if len(steps) else 0.5

    points = [{"start_time": r.start_time.isoformat(),
               "forecast_mw": round(float(r.forecast_mw), 1),
               "wind_low_mw": round(float(r.wind_low), 1),
               "wind_high_mw": round(float(r.wind_high), 1),
               "buy_min_mw": round(float(r.buy_min), 1),
               "buy_mid_mw": round(float(r.buy_mid), 1),
               "buy_max_mw": round(float(r.buy_max), 1)} for r in df.itertuples()]

    tight = df.loc[df["buy_mid"].idxmax()] if len(df) else None
    summary = {
        "step_hours": step_h,
        "avg_mw": {k: round(float(df[c].mean()), 1) for k, c in
                   (("min", "buy_min"), ("mid", "buy_mid"), ("max", "buy_max"))},
        "energy_mwh": {k: round(float(df[c].sum() * step_h), 0) for k, c in
                       (("min", "buy_min"), ("mid", "buy_mid"), ("max", "buy_max"))},
        "tightest": None if tight is None else {
            "start_time": tight["start_time"].isoformat(),
            "min_mw": round(float(tight["buy_min"]), 1),
            "mid_mw": round(float(tight["buy_mid"]), 1),
            "max_mw": round(float(tight["buy_max"]), 1)},
    }
    return {
        "demand_mw": demand_mw, "band": band, "band_label": label,
        "error_band_mw": {"low": round(e_lo, 1), "high": round(e_hi, 1)},
        "calibration": info,
        "backtest": walk_forward_coverage(eval_df, lo_q, hi_q),
        "summary": summary, "points": points,
    }
