from datetime import date

import numpy as np
import pandas as pd

from app.data import Dataset
from app.services import metrics, selection, shortfall, store, views


def ts(value):
    return pd.Timestamp(value, tz="UTC")


def sample_data(start=date(2026, 1, 1), days=31):
    times = pd.date_range(start, periods=days * 48, freq="30min", tz="UTC")
    actual = pd.DataFrame({
        "start_time": times,
        "actual_mw": 7000 + 1500 * np.sin(np.arange(len(times)) / 24),
    })
    rows = []
    for t, value in zip(times, actual.actual_mw):
        for lead in (60, 48, 36, 24, 12, 6):
            rows.append({
                "start_time": t,
                "publish_time": t - pd.Timedelta(hours=lead),
                "generation_mw": value + (lead - 30) * 5,
            })
    return actual, pd.DataFrame(rows)


def test_decision_forecast_uses_latest_publish_before_cutoff():
    fc = pd.DataFrame({
        "start_time": [ts("2026-01-15 12:00")] * 4,
        "publish_time": [ts("2026-01-13 18:00"), ts("2026-01-14 08:00"),
                         ts("2026-01-14 09:00"), ts("2026-01-14 10:00")],
        "generation_mw": [100.0, 200.0, 300.0, 999.0],
    })
    out = selection.decision_forecast(fc, 9.0)
    assert len(out) == 1
    assert out.loc[0, "forecast_mw"] == 300.0
    assert out.loc[0, "horizon_h"] == 27.0


def test_decision_forecast_drops_targets_without_eligible_publications():
    fc = pd.DataFrame({"start_time": [ts("2026-01-15 12:00")],
                       "publish_time": [ts("2026-01-14 09:30")], "generation_mw": [1.0]})
    assert selection.decision_forecast(fc, 9.0).empty


def test_cutoff_hour_changes_selected_publication():
    fc = pd.DataFrame({"start_time": [ts("2026-01-15 12:00")] * 2,
                       "publish_time": [ts("2026-01-14 08:00"), ts("2026-01-14 11:00")],
                       "generation_mw": [1.0, 2.0]})
    assert selection.decision_forecast(fc, 9.0).loc[0, "forecast_mw"] == 1.0
    assert selection.decision_forecast(fc, 12.0).loc[0, "forecast_mw"] == 2.0


def test_error_metrics_known_values():
    fc = pd.DataFrame({"start_time": [ts("2026-01-10 00:00"), ts("2026-01-10 00:30")],
                       "forecast_mw": [110.0, 80.0]})
    actual = pd.DataFrame({"start_time": fc.start_time, "actual_mw": [100.0, 100.0]})
    summary = metrics.summarize(metrics.join_actuals(fc, actual))
    assert summary["n"] == 2
    assert summary["mae_mw"] == 15.0
    assert summary["bias_mw"] == -5.0
    assert summary["rmse_mw"] == round(np.sqrt((100 + 400) / 2), 1)
    assert summary["nmae_pct"] == 15.0


def test_inner_join_ignores_unmatched_rows():
    forecast = pd.DataFrame({"start_time": [ts("2026-01-10 00:00"), ts("2026-01-10 00:30")],
                             "forecast_mw": [1.0, 2.0]})
    actual = pd.DataFrame({"start_time": [ts("2026-01-10 00:00")], "actual_mw": [1.0]})
    assert len(metrics.join_actuals(forecast, actual)) == 1


def test_range_fetch_normalizes_rows_and_filters_to_wind(monkeypatch):
    from app import data
    calls = []

    def fake_request(dataset, params):
        calls.append(dataset)
        if dataset == "FUELHH":
            return [
                {"fuelType": "WIND", "startTime": "2026-01-01T00:00:00Z", "generation": 5000,
                 "publishTime": "2026-01-01T00:30:00Z"},
                {"fuelType": "WIND", "startTime": "2026-01-01T00:00:00Z", "generation": 5100,
                 "publishTime": "2026-01-01T01:00:00Z"},
                {"fuelType": "CCGT", "startTime": "2026-01-01T00:00:00Z", "generation": 9999},
            ]
        return [
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T12:00:00Z", "generation": 4000},
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2025-12-25T12:00:00Z", "generation": 1},
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-02T13:00:00Z", "generation": 2},
        ]

    monkeypatch.setattr(data, "_request", fake_request)
    actual = data._actual(date(2026, 1, 1), date(2026, 1, 1))
    forecast = data._forecast(date(2026, 1, 2), date(2026, 1, 2))
    assert actual.actual_mw.tolist() == [5100]
    assert len(forecast) == 1 and forecast.iloc[0].generation_mw == 4000
    assert calls[0] == "FUELHH" and set(calls[1:]) == {"WINDFOR"}


def test_metrics_and_shortfall_use_generated_frames(monkeypatch):
    actual, forecast = sample_data()
    monkeypatch.setattr(store, "dataset", lambda start, end: Dataset(actual, forecast))
    evaluated = store.evaluation(date(2026, 1, 1), date(2026, 1, 31), 9)
    assert evaluated["day"].nunique() == 31
    assert (evaluated.publish_time <= evaluated.cutoff_time).all()
    assert len(metrics.breakdown("hour", evaluated, evaluated)) == 24
    assert len(metrics.breakdown("day", evaluated, evaluated)) == 31
    assert sum(b["count"] for b in metrics.distribution(evaluated)["bins"]) == len(evaluated)

    day = pd.Timestamp("2026-01-20")
    one_day = evaluated[evaluated.day == day]
    result = shortfall.compute(one_day, evaluated, day, 9000, "p10_p90")
    assert result["calibration"]["method"] == "walk_forward"
    assert all(p["buy_min_mw"] <= p["buy_mid_mw"] <= p["buy_max_mw"]
               for p in result["points"])


def test_views_use_selected_date_range(monkeypatch):
    actual, forecast = sample_data()
    monkeypatch.setattr(store, "dataset", lambda start, end: Dataset(actual, forecast))
    meta = views.meta()
    assert meta["default_start_day"] == "2026-01-01"
    result = views.decision(date(2026, 1, 14), 9, date(2026, 1, 1), date(2026, 1, 31))
    assert result["summary"]["n_points"] == 48
    assert result["summary"]["cutoff_time"].startswith("2026-01-13T09:00")
    summary = views.accuracy_summary(date(2026, 1, 5), date(2026, 1, 10), 9)
    assert summary["n"] == 6 * 48
    assert summary["start"] == "2026-01-05"
    assert len(views.accuracy_breakdown("hour", date(2026, 1, 1), date(2026, 1, 31), 9)["rows"]) == 24


def test_views_reject_invalid_date_ranges():
    for start, end in ((date(2026, 2, 1), date(2026, 1, 1)),
                       (date(2025, 1, 1), date(2026, 1, 2))):
        try:
            views.accuracy_summary(start, end, 9)
        except views.NotFound:
            continue
        raise AssertionError("expected NotFound")
