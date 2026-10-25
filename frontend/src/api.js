const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path, options) {
  let response;
  try {
    response = await fetch(BASE + path, options);
  } catch {
    throw new Error(`Cannot reach the API at ${BASE}. Check that the backend is running and VITE_API_URL is correct.`);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // Keep the HTTP status text when the response has no JSON body.
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return response.json();
}

function query(path, params) {
  const values = Object.entries(params).filter(([, value]) => value != null);
  return `${path}?${new URLSearchParams(values)}`;
}

const get = (path, params = {}) => request(query(path, params));

export const api = {
  meta: () => get("/api/meta"),
  decision: (date, cutoff, start, end) => get("/api/forecast/decision", {
    delivery_date: date,
    cutoff_hour: cutoff,
    start,
    end,
  }),
  summary: (cutoff, start, end) => get("/api/accuracy/summary", {
    cutoff_hour: cutoff,
    start,
    end,
  }),
  breakdown: (by, cutoff, start, end) => get("/api/accuracy/breakdown", {
    by,
    cutoff_hour: cutoff,
    start,
    end,
  }),
  distribution: (cutoff, start, end) => get("/api/accuracy/distribution", {
    cutoff_hour: cutoff,
    start,
    end,
  }),
  shortfall: (body) => request("/api/shortfall", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
};
