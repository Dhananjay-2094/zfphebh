# Power Forecast Platform

Live dashboard: [Open the application](https://zfphebh.vercel.app)

API documentation: [Open the FastAPI docs](https://zfphebh.vercel.app/docs).

A day-ahead wind dashboard for a UK energy utility. It fetches national wind forecasts and actuals directly from the Elexon Insights API, shows the forecast available at a selected order deadline, and measures forecast accuracy. The dashboard currently uses a fixed January 2026 analysis range.

## Project structure

```text
power-forecast-platform/
├── backend/
│   ├── app/
│   │   ├── routers/        # FastAPI route definitions
│   │   ├── services/       # Forecast selection, metrics, and buying estimates
│   │   ├── config.py       # Defaults, limits, and CORS settings
│   │   ├── data.py         # Elexon requests and in-memory cache
│   │   └── main.py         # FastAPI application setup
│   ├── tests/              # Backend tests
│   ├── index.py            # Vercel FastAPI entrypoint
│   ├── requirements.txt    # Backend runtime dependencies
│   ├── Dockerfile          # Backend container image
│   └── heroku.yml          # Heroku Docker build configuration
├── frontend/
│   ├── src/
│   │   ├── components/     # Dashboard UI and chart components
│   │   ├── App.jsx         # Dashboard layout and interactions
│   │   ├── api.js          # Backend API client
│   │   ├── format.js       # Date, time, and unit formatting
│   │   ├── hooks.js        # API and input hooks
│   │   └── styles.css      # Dashboard styling and themes
│   ├── index.html          # Frontend HTML entrypoint
│   ├── package.json        # Frontend dependencies and scripts
│   ├── Dockerfile          # Frontend container image
│   └── vite.config.js      # Vite configuration
├── docker-compose.yml      # Runs frontend and backend locally
├── vercel.json             # Builds and routes the frontend and backend in one Vercel project
├── .gitignore              # Excludes virtualenvs, build output, and env files
└── README.md               # Project and setup documentation
```

## Run locally

```bash
docker compose up --build
```

- App: http://localhost:3000
- API docs: http://localhost:8000/docs

Without Docker:

In the first terminal, start the backend:

```bash
cd backend
python -m venv .venv
# Activate the environment, then:
pip install -r requirements.txt
export CORS_ORIGINS=http://localhost:5173
uvicorn app.main:app --reload
```

In a second terminal opened at the repository root, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The Elexon Insights API is called by the backend; no local CSV ingestion is required.

## Using the dashboard

- The initial analysis range is **1–31 January 2026** and the initial delivery day is **14 January 2026**.
- The analysis range start and end are currently fixed and disabled in the UI. The backend API supports ranges up to 366 days, but the dashboard is limited to January for now.
- Pick a delivery day within January and an order deadline in UK local time.
- The forecast chart overlays actual generation by default. Turn it off with the checkbox when you want to view the forecast alone.
- Accuracy is calculated only for half-hours with both a forecast and actual; unmatched periods are excluded.
- Power values and the demand input are shown in **GW**. Daily energy is shown in **GWh**. The API continues to use MW and MWh internally; the frontend converts values for display and converts the entered demand back to MW before sending it to the backend. The optional procurement view estimates a wind shortfall range from forecast errors. It is an indicative wind-only view, not a complete market buying plan.

## Data and calculation

The backend requests `FUELHH` actuals filtered to `WIND` and `WINDFOR` forecast publications from Elexon. Responses are held in a process-local cache for five minutes. Forecast requests include publication dates before the selected delivery range so the app can find the latest forecast published by the D-1 cutoff. Data is fetched again after the cache expires.

For each delivery half-hour, the app selects the latest forecast published at or before the UK-local order cutoff on D-1. Forecast error is `forecast − actual`; positive values mean wind was over-forecast. Accuracy includes MAE, RMSE, bias, normalized MAE, error percentiles, an error distribution, and breakdowns by hour, lead time, delivery day, and forecast level. MAPE is not used because it becomes unstable near zero output.

The optional procurement range converts past forecast error percentiles into low/high wind and buy estimates. When enough earlier days exist, its error band is fitted from earlier dates only. The back-test reports realized coverage on eligible days.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/meta` | Default date range, cutoff, bands, and range limit |
| GET | `/api/forecast/decision?delivery_date=&cutoff_hour=&start=&end=` | Decision-time forecast for a delivery day; `delivery_date` is required, while `start` and `end` are optional |
| GET | `/api/accuracy/summary?start=&end=&cutoff_hour=` | Accuracy summary for a selected delivery range |
| GET | `/api/accuracy/breakdown?by=&start=&end=&cutoff_hour=` | Accuracy sliced by hour, horizon, day, or wind level |
| GET | `/api/accuracy/distribution?start=&end=&cutoff_hour=` | Error histogram and percentiles |
| POST | `/api/shortfall` | Wind shortfall range using delivery date, selected range, demand, band, and cutoff |
| GET | `/api/health` | Health check |

Elexon request failures return HTTP 502. Invalid ranges return HTTP 422.

## Deployment

The backend needs outbound HTTPS access to `data.elexon.co.uk`. The root `vercel.json` configures the frontend and backend as services in one Vercel project. It routes `/api/*` requests to FastAPI and sends other app routes to the Vite frontend. It should also route `/docs`, `/openapi.json`, and optionally `/redoc` to the backend so the API documentation and its schema are available on the shared domain. Keep the backend routes before the frontend catch-all rewrite.

For the combined Vercel deployment, set `VITE_API_URL` to the deployment origin (for example, `https://zfphebh.vercel.app`) so the frontend calls the backend through the same domain. `backend/index.py` exposes the FastAPI application and `backend/requirements.txt` lists its dependencies. Because frontend and API share an origin, a separate CORS origin is not normally needed for browser requests. Docker Compose remains available for local development.

For Heroku, the backend is in a monorepo subdirectory and must be deployed with `backend/` as the app root (for example, by pushing a Git subtree). The existing `backend/Dockerfile` and `backend/heroku.yml` configure a Docker-based Heroku build.

## Current scope

- National wind only, sourced from Elexon; no demand forecasts, other generation, prices, or contract positions.
- The procurement input is a single flat demand value for every half-hour.
- Elexon availability and publication delays determine whether a requested date has forecast or actual data.
- The cache is in memory per backend process and is not shared across multiple instances.

## AI tool usage

Codex was used as a discussion and coding assistant during development:

- After reviewing the brief and doing initial background reading, I used Codex to expand the requirements, identify possible omissions, and refine the scope through discussion.
- I selected the architecture, design, and technology stack, then discussed possible improvements with Codex.
- I created the repository and project skeleton, started with simpler functions, and mapped the data flow before moving into the main implementation.
- I used Codex for coding assistance and iterative reviews while building the backend, frontend, and forecast-accuracy metrics, then worked through issues and refinements together.
- We considered using one API for the dashboard, then chose separate endpoints for different functions so each action could request the data it needed without repeatedly fetching unrelated data.
- Because forecasts are hourly while actual generation is half-hourly, we considered matching values by period start time or averaging consecutive actual readings into hourly values. I chose to match by period start time for the calculations.
- I chose to display power in GW instead of MW because national generation figures are easier to read at that scale. The frontend converts the values for display while the backend continues to use MW for calculations; daily energy is displayed in GWh.

I reviewed the suggestions and made the final implementation decisions.
