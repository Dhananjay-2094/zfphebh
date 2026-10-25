import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { COLORS, gw, hhmm } from "../format.js";

const axis = {
  tick: { fill: COLORS.muted, fontSize: 12 },
  tickLine: false,
  axisLine: { stroke: COLORS.rule },
};
const gwTick = (v) => (v / 1000).toLocaleString("en-GB");
const yLabel = (value) => ({
  value,
  angle: -90,
  position: "insideLeft",
  fill: COLORS.muted,
  fontSize: 12,
  dy: 20,
});
const tip = {
  contentStyle: {
    border: `1px solid ${COLORS.rule}`,
    borderRadius: 4,
    fontSize: 13,
  },
};
const powerFmt = (v, name) => [`${gw(v, 2)} GW`, name];

export function DecisionChart({ points, showActual }) {
  const data = points.map((point) => ({
    label: hhmm(point.start_time),
    forecast: point.forecast_mw,
    actual: point.actual_mw,
  }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
        <CartesianGrid stroke={COLORS.rule} vertical={false} />
        <XAxis dataKey="label" interval={Math.max(0, Math.ceil(data.length / 12) - 1)} {...axis} />
        <YAxis tickFormatter={gwTick} width={48} label={yLabel("GW")} {...axis} />
        <Tooltip formatter={powerFmt} {...tip} />
        <Line
          dataKey="forecast"
          name="Forecast"
          stroke={COLORS.forecast}
          strokeWidth={2.75}
          dot={false}
        />
        {showActual && (
          <Line
            dataKey="actual"
            name="Actually generated"
            stroke={COLORS.actual}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
          />
        )}
        {showActual && <Legend verticalAlign="top" height={28} />}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function BreakdownChart({ rows }) {
  const many = rows.length > 12;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
        <CartesianGrid stroke={COLORS.rule} vertical={false} />
        <XAxis dataKey="key" interval={many ? "preserveStartEnd" : 0} minTickGap={14} {...axis} />
        <YAxis tickFormatter={gwTick} width={48} label={yLabel("GW")} {...axis} />
        <Tooltip formatter={powerFmt} {...tip} />
        <Legend verticalAlign="top" height={28} />
        <ReferenceLine y={0} stroke={COLORS.muted} />
        <Bar
          dataKey="mae_mw"
          name="Typical miss (MAE)"
          fill={COLORS.forecast}
          radius={[2, 2, 0, 0]}
        />
        <Bar
          dataKey="rmse_mw"
          name="Big-miss weighted (RMSE)"
          fill="#9CC9CE"
          radius={[2, 2, 0, 0]}
        />
        <Line
          dataKey="bias_mw"
          name="Lean (bias)"
          stroke={COLORS.amber}
          strokeWidth={2}
          dot={!many}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function Histogram({ dist }) {
  const { bins, p10_mw: lo, p90_mw: hi } = dist;
  return (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart data={bins} margin={{ top: 8, right: 12, bottom: 18, left: 4 }} barCategoryGap={1}>
        <CartesianGrid stroke={COLORS.rule} vertical={false} />
        <XAxis
          dataKey="mid"
          tickFormatter={(value) => gw(value)}
          interval="preserveStartEnd"
          minTickGap={24}
          label={{
            value: "Forecast minus actual (GW)",
            position: "insideBottom",
            dy: 16,
            fill: COLORS.muted,
            fontSize: 12,
          }}
          {...axis}
        />
        <YAxis width={40} allowDecimals={false} {...axis} />
        <Tooltip
          formatter={(value) => [`${value} half-hours`, "Count"]}
          labelFormatter={(value) => `Around ${gw(value, 2)} GW`}
          {...tip}
        />
        <Bar dataKey="count" radius={[2, 2, 0, 0]}>
          {bins.map((b) => (
            <Cell key={b.mid} fill={b.mid >= lo && b.mid <= hi ? COLORS.forecast : COLORS.histogramMuted} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function BuyChart({ points }) {
  const data = points.map((point) => ({
    label: hhmm(point.start_time),
    base: point.buy_min_mw,
    band: Math.max(0, point.buy_max_mw - point.buy_min_mw),
    mid: point.buy_mid_mw,
    min: point.buy_min_mw,
    max: point.buy_max_mw,
  }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
        <CartesianGrid stroke={COLORS.rule} vertical={false} />
        <XAxis dataKey="label" interval={Math.max(0, Math.ceil(data.length / 12) - 1)} {...axis} />
        <YAxis tickFormatter={gwTick} width={48} label={yLabel("GW to buy")} {...axis} />
        <Tooltip
          {...tip}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <div className="tip">
                <strong>{label}</strong>
                <div>Buy {gw(payload[0].payload.min, 2)} to {gw(payload[0].payload.max, 2)} GW</div>
                <div>Central estimate {gw(payload[0].payload.mid, 2)} GW</div>
              </div>
            ) : null
          }
        />
        <Area dataKey="base" stackId="b" stroke="none" fill="transparent" isAnimationActive={false} />
        <Area
          dataKey="band"
          stackId="b"
          stroke="none"
          fill={COLORS.buy}
          fillOpacity={0.22}
          isAnimationActive={false}
        />
        <Line dataKey="mid" stroke={COLORS.buy} strokeWidth={2.5} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
