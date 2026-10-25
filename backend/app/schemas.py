from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import DEFAULT_BAND, DEFAULT_CUTOFF_HOUR, DEFAULT_END_DAY, DEFAULT_START_DAY


class ShortfallRequest(BaseModel):
    delivery_date: date
    start_date: date = DEFAULT_START_DAY
    end_date: date = DEFAULT_END_DAY
    demand_mw: float = Field(gt=0, le=100_000, description="Expected demand, flat across the day")
    band: Literal["p05_p95", "p10_p90", "p25_p75"] = DEFAULT_BAND
    cutoff_hour: float = Field(default=DEFAULT_CUTOFF_HOUR, ge=0, le=23.5)

    @model_validator(mode="after")
    def delivery_inside_range(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        if not self.start_date <= self.delivery_date <= self.end_date:
            raise ValueError("delivery_date must be within the selected date range")
        return self
