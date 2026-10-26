from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.config import DEFAULT_CUTOFF_HOUR, DEFAULT_END_DAY, DEFAULT_START_DAY
from app.schemas import ShortfallRequest
from app.services import views

router = APIRouter(prefix="/api")
Cutoff = Query(DEFAULT_CUTOFF_HOUR, ge=0, le=23.5, description="UK-local hour on D-1")
Start = Query(DEFAULT_START_DAY, description="First delivery day in the selected range")
End = Query(DEFAULT_END_DAY, description="Last delivery day in the selected range")


def _run(fn, *a):
    # Translate expected service exceptions into appropriate HTTP error responses.
    try:
        return fn(*a)
    except views.NotFound as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except views.UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/health")
def health():
    # Report that the API process is responding.
    return {"status": "ok"}


@router.get("/meta")
def meta():
    # Return API defaults, supported bands, timezone, and error sign convention.
    return views.meta()


@router.get("/forecast/decision")
def forecast_decision(delivery_date: date, cutoff_hour: float = Cutoff,
                       start: date | None = None, end: date | None = None):
    # Return the latest eligible forecast for each period on a delivery date.
    return _run(views.decision, delivery_date, cutoff_hour, start, end)


@router.get("/accuracy/summary")
def accuracy_summary(start: date = Start, end: date = End, cutoff_hour: float = Cutoff):
    # Build the aggregate accuracy response for a selected range and cutoff.
    return _run(views.accuracy_summary, start, end, cutoff_hour)


@router.get("/accuracy/breakdown")
def accuracy_breakdown(by: Literal["hour", "horizon", "day", "wind_level"],
                       start: date = Start, end: date = End, cutoff_hour: float = Cutoff):
    # Build grouped accuracy output, translating invalid grouping requests.
    return _run(views.accuracy_breakdown, by, start, end, cutoff_hour)


@router.get("/accuracy/distribution")
def accuracy_distribution(start: date = Start, end: date = End, cutoff_hour: float = Cutoff):
    # Build the error distribution response for a selected range and cutoff.
    return _run(views.accuracy_distribution, start, end, cutoff_hour)


@router.post("/shortfall")
def shortfall(req: ShortfallRequest):
    # Validate and dispatch a shortfall estimation request.
    return _run(views.shortfall_view, req.delivery_date, req.start_date, req.end_date,
                req.demand_mw, req.band, req.cutoff_hour)
