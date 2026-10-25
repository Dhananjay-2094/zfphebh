import { useEffect, useState } from "react";
import { api } from "./api.js";
import { BreakdownChart, BuyChart, DecisionChart, Histogram } from "./components/charts.jsx";
import { Readouts, Section, Status } from "./components/ui.jsx";
import { addDays, dayLabel, gw, hhmm, hourLabel, shortDay, stamp } from "./format.js";
import { useApi, useDebounced } from "./hooks.js";

const CUTOFF_OPTIONS = Array.from({ length: 13 }, (_, i) => 6 + i * 0.5); // 06:00 to 12:00
const MAX_DEMAND_GW = 100;
const SLICES = [
  { key: "hour", label: "Time of day",
    note: "Each bar is one hour of the day. Look for hours where forecasts are consistently weaker." },
  { key: "horizon", label: "How far ahead",
    note: "Accuracy by how long before delivery the forecast was published. Forecasts made earlier miss by more." },
  { key: "day", label: "Day",
    note: "One bar per delivery day in the selected range. Tall bars are days when the weather surprised the forecast." },
  { key: "wind_level", label: "Wind level",
    note: "Accuracy when the forecast itself was low, medium or high, so you can see where risk concentrates." },
];

export default function App() {
  const meta = useApi(() => api.meta(), []);
  const [theme, setTheme] = useState(() => localStorage.getItem("wind-desk-theme") || "light");
  const [day, setDay] = useState(null);
  const [rangeStart, setRangeStart] = useState(null);
  const [rangeEnd, setRangeEnd] = useState(null);
  const [cutoff, setCutoff] = useState(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("wind-desk-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!meta.data) return;
    const {
      default_start_day,
      default_end_day,
      default_delivery_day,
      default_cutoff_hour,
    } = meta.data;
    setRangeStart((d) => d ?? default_start_day);
    setRangeEnd((d) => d ?? default_end_day);
    setDay((d) => d ?? default_delivery_day);
    setCutoff((c) => c ?? default_cutoff_hour);
  }, [meta.data]);

  if (meta.error) return <main className="solo"><Status state={meta} /></main>;
  if (!meta.data || day == null || rangeStart == null || rangeEnd == null || cutoff == null)
    return <main className="solo"><p className="status">Loading…</p></main>;

  const m = meta.data;
  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">≋</span>
          <div>
            <h1>Power Forecast</h1>
            <p className="tag">DAY-AHEAD WIND DESK</p>
          </div>
        </div>
        <div className="field">
          <label htmlFor="range-start">Analysis range start</label>
          <input id="range-start" type="date" value={rangeStart} disabled />
        </div>
        <div className="field">
          <label htmlFor="range-end">Analysis range end</label>
          <input id="range-end" type="date" value={rangeEnd} disabled />
        </div>

        <div className="field">
          <label htmlFor="day">Delivery day (within range)</label>
          <div className="stepper">
            <button type="button" aria-label="Previous day" disabled={day <= rangeStart}
                    onClick={() => setDay(addDays(day, -1))}>‹</button>
            <input id="day" type="date" min={rangeStart} max={rangeEnd} value={day}
                   onChange={(e) => e.target.value && setDay(e.target.value)} />
            <button type="button" aria-label="Next day" disabled={day >= rangeEnd}
                    onClick={() => setDay(addDays(day, 1))}>›</button>
          </div>
        </div>

        <div className="field">
          <label htmlFor="cutoff">Order deadline, day before (UK time)</label>
          <select id="cutoff" value={cutoff} onChange={(e) => setCutoff(Number(e.target.value))}>
            {CUTOFF_OPTIONS.map((h) => <option key={h} value={h}>{hourLabel(h)}</option>)}
          </select>
        </div>

        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Sections">
          <a href="#forecast"><span aria-hidden="true">⌁</span> Wind overview</a>
          <a href="#accuracy"><span aria-hidden="true">◉</span> Forecast accuracy</a>
          <a href="#buy"><span aria-hidden="true">◷</span> Buying estimate</a>
        </nav>
        <p className="fine">Times are UK local. Forecast error is forecast minus actual, so a positive
          error means the forecast was too high.</p>
      </aside>

      <main>
        <div className="dashboard-toolbar">
          <button
            className="theme-toggle"
            type="button"
            aria-pressed={theme === "dark"}
            onClick={() => setTheme((current) => current === "dark" ? "light" : "dark")}
          >
            <span aria-hidden="true">{theme === "dark" ? "☀" : "◐"}</span>
            {theme === "dark" ? "Light appearance" : "Dark appearance"}
          </button>
        </div>
        <ForecastSection day={day} cutoff={cutoff} start={rangeStart} end={rangeEnd} />
        <AccuracySection cutoff={cutoff} start={rangeStart} end={rangeEnd} />
        <BuySection meta={m} day={day} cutoff={cutoff} start={rangeStart} end={rangeEnd} />
      </main>
    </div>
  );
}

function ForecastSection({ day, cutoff, start, end }) {
  const [showActual, setShowActual] = useState(true);
  const d = useApi(() => api.decision(day, cutoff, start, end), [day, cutoff, start, end]);
  const s = d.data?.summary;
  return (
    <Section id="forecast" title={`Wind forecast for ${dayLabel(day)}`}
      intro={s
        ? `This is the latest forecast published before ${stamp(s.cutoff_time)}, which is what you would have had when placing the day-ahead order. Later forecasts exist but were not available to you.`
        : "The latest forecast published before your order deadline."}>
      <Status state={d}>
        {s && (
          <>
            <Readouts items={[
              { label: "Average wind", value: `${gw(s.avg_mw)} GW` },
              { label: "Peak", value: `${gw(s.peak_mw)} GW`, hint: `at ${hhmm(s.peak_time)}` },
              { label: "Lowest", value: `${gw(s.low_mw)} GW`, hint: `at ${hhmm(s.low_time)}` },
              { label: "Newest forecast used", value: hhmm(s.last_publish),
                hint: `published ${shortDay(s.last_publish)}, before your deadline` },
            ]} />
            <div className="plot"><DecisionChart points={d.data.points} showActual={showActual} /></div>
            <label className="check">
              <input type="checkbox" checked={showActual} onChange={(e) => setShowActual(e.target.checked)} />
              Overlay what was actually generated (only knowable in hindsight)
            </label>
          </>
        )}
      </Status>
    </Section>
  );
}

function AccuracySection({ cutoff, start, end }) {
  const [slice, setSlice] = useState("hour");
  const sum = useApi(() => api.summary(cutoff, start, end), [cutoff, start, end]);
  const bd = useApi(() => api.breakdown(slice, cutoff, start, end), [slice, cutoff, start, end]);
  const dist = useApi(() => api.distribution(cutoff, start, end), [cutoff, start, end]);
  const s = sum.data;
  const lean = s && (Math.abs(s.bias_mw) < 0.02 * s.mean_actual_mw ? "Roughly balanced"
    : s.bias_mw > 0 ? "Forecasts ran high" : "Forecasts ran low");
  const note = SLICES.find((x) => x.key === slice).note;
  return (
    <Section id="accuracy" title="How far off these forecasts have been"
      intro={`Selected delivery dates ${start} to ${end}, comparing the forecast available at the deadline with actual wind generation.`}>
      <Status state={sum} height={90}>
        {s && s.n === 0 && <p className="status">No matched actuals and forecasts are available for this date range yet.</p>}
        {s && s.n > 0 && (
          <Readouts items={[
            { label: "Typical miss (MAE)", value: `${gw(s.mae_mw, 2)} GW`, hint: `${s.nmae_pct}% of average output` },
            { label: "Big-miss measure (RMSE)", value: `${gw(s.rmse_mw, 2)} GW`,
              hint: s.rmse_mw > 1.3 * s.mae_mw ? "well above the typical miss, so some errors are large" : "close to the typical miss" },
            { label: "Lean (bias)", value: `${s.bias_mw > 0 ? "+" : ""}${gw(s.bias_mw, 2)} GW`, hint: lean },
            { label: "Middle 80% of misses", value: `${gw(s.error_p10_mw, 2)} to ${gw(s.error_p90_mw, 2)} GW`,
              hint: "forecast minus actual" },
            { label: "Half-hours checked", value: s.n.toLocaleString("en-GB") },
          ]} />
        )}
      </Status>

      <div className="tabs" role="tablist" aria-label="Break the error down by">
        {SLICES.map((x) => (
          <button key={x.key} role="tab" aria-selected={slice === x.key}
                  className={slice === x.key ? "on" : ""} onClick={() => setSlice(x.key)}>
            {x.label}
          </button>
        ))}
      </div>
      <Status state={bd}>
        {bd.data && <div className="plot"><BreakdownChart rows={bd.data.rows} /></div>}
      </Status>
      <p className="note">{note}</p>

      <h3>How big the misses are</h3>
      <p className="note">Teal bars hold the middle 80% of misses. Bars to the right are forecasts that
        were too high, so wind under-delivered.</p>
      <Status state={dist} height={260}>
        {dist.data && <div className="plot"><Histogram dist={dist.data} /></div>}
      </Status>
    </Section>
  );
}

function BuySection({ meta, day, cutoff, start, end }) {
  const [demand, setDemand] = useState("");
  const [demandCapped, setDemandCapped] = useState(false);
  const [band, setBand] = useState(meta.default_band);
  const debounced = useDebounced(demand);
  const demandMw = parseFloat(debounced) * 1000;
  const overDemandLimit = Number.isFinite(demandMw) && demandMw > MAX_DEMAND_GW * 1000;
  const valid = Number.isFinite(demandMw) && demandMw > 0 && demandMw <= MAX_DEMAND_GW * 1000;
  const r = useApi(
    () => (valid
      ? api.shortfall({
          delivery_date: day,
          start_date: start,
          end_date: end,
          demand_mw: demandMw,
          band,
          cutoff_hour: cutoff,
        })
      : Promise.resolve(null)),
    [day, cutoff, demandMw, band],
  );
  const s = r.data?.summary;
  const bt = r.data?.backtest;
  return (
    <Section id="buy" title="How much to buy"
      intro="Enter the demand you expect to serve. The app subtracts the forecast wind and widens the answer by how wrong forecasts have been, so you get a range rather than one falsely precise number. It covers wind only: other generation, imports and your own contracts are not in this data.">
      <div className="inputs">
        <div className="field">
          <label htmlFor="demand">Expected demand (GW, same for every hour)</label>
          <input id="demand" type="number" min="0" max={MAX_DEMAND_GW} step="0.5" inputMode="decimal"
                 placeholder="e.g. 30" value={demand}
                 onChange={(e) => {
                   setDemand(e.target.value);
                   setDemandCapped(false);
                 }}
                 onBlur={(e) => {
                   const value = Number(e.target.value);
                   if (Number.isFinite(value) && value > MAX_DEMAND_GW) {
                     setDemand(String(MAX_DEMAND_GW));
                     setDemandCapped(true);
                   }
                 }} />
        </div>
        <div className="field">
          <label htmlFor="band">Safety margin</label>
          <select id="band" value={band} onChange={(e) => setBand(e.target.value)}>
            {meta.bands.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}
          </select>
        </div>
      </div>

      {demandCapped && <p className="status" role="status">Demand was capped at 100 GW, the maximum allowed.</p>}
      {overDemandLimit && !demandCapped &&
        <p className="status" role="status">The maximum is 100 GW. This value will be capped when you leave the field.</p>}
      {!valid && !overDemandLimit &&
        <p className="status">Enter a demand figure to see how much you would need to buy.</p>}
      {valid && (
        <Status state={r}>
          {s && (
            <>
              <Readouts items={[
                { label: "Average to buy", value: `${gw(s.avg_mw.min)} to ${gw(s.avg_mw.max)} GW`,
                  hint: `central estimate ${gw(s.avg_mw.mid)} GW` },
                { label: "Tightest half-hour", value: `${gw(s.tightest.min_mw)} to ${gw(s.tightest.max_mw)} GW`,
                  hint: `at ${hhmm(s.tightest.start_time)}` },
                { label: "Energy for the day", value: `${gw(s.energy_mwh.min)} to ${gw(s.energy_mwh.max)} GWh`,
                  hint: `central ${gw(s.energy_mwh.mid)} GWh` },
              ]} />
              <div className="plot"><BuyChart points={r.data.points} /></div>
              <p className="note">
                The shaded band is the range to buy; the line is the central estimate. The band assumes wind
                could land up to {gw(r.data.error_band_mw.high)} GW below or {gw(-r.data.error_band_mw.low)} GW
                {" "}above the forecast, the spread seen over {r.data.calibration.days_used} days of history.
                {r.data.calibration.method === "in_sample" &&
                  " Too few earlier days exist for this date, so the selected range was used and the band is optimistic."}
                {bt?.coverage_pct != null &&
                  ` Tested day by day on available actuals, wind stayed inside a band like this ${bt.coverage_pct}% of the time (aimed for ${bt.target_pct}%).`}
              </p>
            </>
          )}
        </Status>
      )}
    </Section>
  );
}
