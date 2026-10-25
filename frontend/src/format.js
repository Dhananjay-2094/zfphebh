const TZ = "Europe/London";

export const mw = (v) => (v == null ? "–" : Math.round(v).toLocaleString("en-GB"));
export const gw = (v, d = 1) =>
  v == null ? "–" : (v / 1000).toLocaleString("en-GB", { maximumFractionDigits: d });
export const hhmm = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
export const stamp = (iso) =>
  new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: TZ,
  });
export const shortDay = (iso) =>
  new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: TZ });
export const dayLabel = (isoDate) =>
  new Date(isoDate + "T12:00:00Z").toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
export const addDays = (isoDate, n) => {
  const d = new Date(isoDate + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
export const hourLabel = (h) => `${String(Math.floor(h)).padStart(2, "0")}:${h % 1 ? "30" : "00"}`;

export const COLORS = {
  ink: "var(--ink)",
  muted: "var(--muted)",
  rule: "var(--rule)",
  forecast: "var(--forecast)",
  actual: "var(--actual)",
  amber: "var(--amber)",
  buy: "var(--buy)",
  histogramMuted: "var(--histogram-muted)",
};
