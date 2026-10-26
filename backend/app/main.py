from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers.api import router

app = FastAPI(
    title="Power Forecast API",
    description="Day-ahead UK wind forecasts and accuracy from Elexon.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root():
    # Return basic service metadata and links to the API docs and health endpoint.
    return {"name": "power-forecast-api", "docs": "/docs", "health": "/api/health"}
