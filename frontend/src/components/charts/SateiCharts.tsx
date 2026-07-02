import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LineChart, Line, ResponsiveContainer, ReferenceLine, Cell,
  AreaChart, Area,
} from "recharts";

// ── 1. Comp Price Comparison Bar Chart ──────────────────────────────────

interface CompChartData {
  address: string;
  raw_price: number;
  adjusted_price: number;
  adjustment_pct: number;
}

interface CompPriceChartProps {
  comps: CompChartData[];
  sateiPrice: number;
}

export function CompPriceChart({ comps, sateiPrice }: CompPriceChartProps) {
  const data = comps.map((c) => ({
    name: c.address || "Comp",
    "Raw Price": c.raw_price / 10000,
    "Adjusted Price": c.adjusted_price / 10000,
    adj: c.adjustment_pct,
  }));

  const formatMan = (v: number) => `¥${v.toLocaleString()}万`;

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
        Comp Price Comparison (万円)
      </h3>
      <ResponsiveContainer width="100%" height={Math.max(200, comps.length * 50 + 60)}>
        <BarChart data={data} layout="vertical" margin={{ left: 100, right: 40, top: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tickFormatter={formatMan} />
          <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => formatMan(v)} />
          <Legend />
          <Bar dataKey="Raw Price" fill="#94a3b8" barSize={14} />
          <Bar dataKey="Adjusted Price" fill="#2563eb" barSize={14} />
          <ReferenceLine x={sateiPrice / 10000} stroke="#dc2626" strokeWidth={2} strokeDasharray="5 5" label={{ value: `Satei: ${formatMan(sateiPrice / 10000)}`, position: "top", fill: "#dc2626", fontSize: 11 }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 2. Price-vs-Probability Curve Line Chart ────────────────────────────

interface ProbabilityPoint {
  asking_price_yen: number;
  premium_pct: number;
  p30: number;
  p60: number;
  p90: number;
  p180: number;
  expected_days: number;
  expected_settlement_yen: number;
}

interface PriceProbabilityCurveChartProps {
  points: ProbabilityPoint[];
  sateiPrice: number;
  sweetSpotYen: number | null;
}

export function PriceProbabilityCurveChart({ points, sateiPrice, sweetSpotYen }: PriceProbabilityCurveChartProps) {
  void sateiPrice;
  void sweetSpotYen;

  const data = points.map((pt) => ({
    price: `${pt.premium_pct >= 0 ? "+" : ""}${pt.premium_pct}%`,
    priceYen: pt.asking_price_yen,
    "30 days": Math.round(pt.p30 * 100),
    "60 days": Math.round(pt.p60 * 100),
    "90 days": Math.round(pt.p90 * 100),
    "180 days": Math.round(pt.p180 * 100),
    days: pt.expected_days,
  }));

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
        Settlement Probability by Asking Price
      </h3>
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="price" tick={{ fontSize: 11 }} label={{ value: "Premium over satei", position: "insideBottom", offset: -5, fontSize: 11 }} />
          <YAxis domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} label={{ value: "P(close)", angle: -90, position: "insideLeft", fontSize: 11 }} />
          <Tooltip formatter={(v: number) => `${v}%`} />
          <Legend />
          <Area type="monotone" dataKey="180 days" stroke="#60a5fa" fill="#dbeafe" strokeWidth={2} />
          <Area type="monotone" dataKey="90 days" stroke="#2563eb" fill="#bfdbfe" strokeWidth={2} />
          <Area type="monotone" dataKey="60 days" stroke="#7c3aed" fill="#ede9fe" strokeWidth={2} />
          <Area type="monotone" dataKey="30 days" stroke="#dc2626" fill="#fee2e2" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 3. Days-on-Market Chart ─────────────────────────────────────────────

interface DaysOnMarketChartProps {
  points: ProbabilityPoint[];
}

export function DaysOnMarketChart({ points }: DaysOnMarketChartProps) {
  const data = points.map((pt) => ({
    price: `${pt.premium_pct >= 0 ? "+" : ""}${pt.premium_pct}%`,
    "Expected Days": pt.expected_days,
    "Settlement (万)": Math.round(pt.expected_settlement_yen / 10000),
  }));

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
        Expected Days on Market & Settlement Price
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 10, right: 40, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="price" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="days" orientation="left" label={{ value: "Days", angle: -90, position: "insideLeft", fontSize: 11 }} />
          <YAxis yAxisId="price" orientation="right" tickFormatter={(v: number) => `¥${v.toLocaleString()}万`} label={{ value: "Settlement", angle: 90, position: "insideRight", fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line yAxisId="days" type="monotone" dataKey="Expected Days" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4 }} />
          <Line yAxisId="price" type="monotone" dataKey="Settlement (万)" stroke="#059669" strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 4. Negotiation Scenario Visualization ───────────────────────────────

interface ScenarioData {
  scenario_label: string;
  opening_price_yen: number;
  settlement_price_yen: number | null;
  settled: boolean;
  rounds: number;
  concession_path: number[];
  zopa_low_yen: number | null;
  zopa_high_yen: number | null;
}

interface NegotiationScenarioChartProps {
  scenarios: ScenarioData[];
  askingPrice: number;
  reservationPrice: number;
}

export function NegotiationScenarioChart({ scenarios, askingPrice, reservationPrice }: NegotiationScenarioChartProps) {
  const maxRounds = Math.max(...scenarios.map((s) => s.concession_path.length));
  const data = Array.from({ length: maxRounds }, (_, i) => {
    const point: Record<string, number | string> = { round: `R${i + 1}` };
    scenarios.forEach((s) => {
      if (i < s.concession_path.length) {
        point[s.scenario_label] = Math.round(s.concession_path[i] / 10000);
      }
    });
    return point;
  });

  const colors = ["#2563eb", "#059669", "#dc2626", "#f59e0b", "#7c3aed"];

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
        Negotiation Scenario Paths (万円)
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="round" tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={(v: number) => `¥${v.toLocaleString()}万`} />
          <Tooltip formatter={(v: number) => `¥${v.toLocaleString()}万`} />
          <Legend />
          <ReferenceLine y={askingPrice / 10000} stroke="#333" strokeDasharray="5 5" label={{ value: "Asking", position: "right", fontSize: 10 }} />
          <ReferenceLine y={reservationPrice / 10000} stroke="#dc2626" strokeDasharray="5 5" label={{ value: "Walk-away", position: "right", fontSize: 10 }} />
          {scenarios.map((s, i) => (
            <Line key={s.scenario_label} type="monotone" dataKey={s.scenario_label} stroke={colors[i % colors.length]} strokeWidth={2} dot={{ r: 3 }} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Summary cards */}
      <div style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
        {scenarios.map((s, i) => (
          <div key={s.scenario_label} style={{
            padding: 12, borderRadius: 8, border: `2px solid ${colors[i % colors.length]}`,
            background: s.settled ? "#f0fdf4" : "#fef2f2", minWidth: 180, flex: 1,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: colors[i % colors.length] }}>{s.scenario_label}</div>
            <div style={{ fontSize: 12, color: "#555", marginTop: 4 }}>
              {s.settled
                ? `Settled at ¥${Math.round((s.settlement_price_yen || 0) / 10000).toLocaleString()}万 (${s.rounds} rounds)`
                : `No settlement after ${s.rounds} rounds`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 5. Concession Ladder Visualization ──────────────────────────────────

interface ConcessionLadderProps {
  ladder: number[];
  askingPrice: number;
  walkAwayPrice: number;
  clientRole: string;
}

export function ConcessionLadderChart({ ladder, askingPrice, walkAwayPrice, clientRole }: ConcessionLadderProps) {
  const data = ladder.map((price, i) => ({
    step: `Step ${i + 1}`,
    "Price (万)": Math.round(price / 10000),
  }));

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
        Recommended Concession Ladder ({clientRole === "seller" ? "Descending" : "Ascending"})
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="step" tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={(v: number) => `¥${v.toLocaleString()}万`} />
          <Tooltip formatter={(v: number) => `¥${v.toLocaleString()}万`} />
          <ReferenceLine y={askingPrice / 10000} stroke="#2563eb" strokeDasharray="5 5" label={{ value: "Asking", position: "right", fontSize: 10 }} />
          <ReferenceLine y={walkAwayPrice / 10000} stroke="#dc2626" strokeDasharray="5 5" label={{ value: "Walk-away", position: "right", fontSize: 10 }} />
          <Bar dataKey="Price (万)" barSize={30}>
            {data.map((_, i) => (
              <Cell key={i} fill={i === 0 ? "#2563eb" : i === data.length - 1 ? "#dc2626" : "#60a5fa"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
