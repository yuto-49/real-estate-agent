import { useState, useEffect, useCallback } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// ---------- Types ----------

interface PropertyOption {
  id: string;
  address: string;
  asking_price: number;
}

interface SegmentData {
  life_stage: string;
  count: number;
  avg_bid_yen: number;
  median_bid_yen: number;
  win_rate: number;
}

interface BidBucket {
  low_yen: number;
  high_yen: number;
  count: number;
}

interface BuyerSimResult {
  property_id: string;
  gnn_valuation_yen: number;
  gnn_confidence_low_yen: number;
  gnn_confidence_high_yen: number;
  satei_price_yen: number | null;
  price_probability_sweet_spot_yen: number | null;
  buyer_segments: SegmentData[];
  bid_histogram: BidBucket[];
  median_bid_yen: number;
  mean_bid_yen: number;
  hazard_impact_pct: number;
  rounds_to_converge: number;
  narrative_jp: string;
}

// ---------- Helpers ----------

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const SEGMENT_COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#ef4444", "#10b981"];
const LIFE_STAGE_LABELS: Record<string, string> = {
  first_time: "初回購入者",
  upgrade: "住み替え",
  investor: "投資家",
  retiree: "リタイア層",
};

function formatYen(yen: number): string {
  if (yen >= 100_000_000) {
    return `${(yen / 100_000_000).toFixed(2)}億円`;
  }
  if (yen >= 10_000) {
    return `${(yen / 10_000).toLocaleString("ja-JP", { maximumFractionDigits: 0 })}万円`;
  }
  return `¥${yen.toLocaleString("ja-JP")}`;
}

// ---------- Component ----------

export default function BuyerSimPage() {
  const [properties, setProperties] = useState<PropertyOption[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [nBuyers, setNBuyers] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BuyerSimResult | null>(null);

  // Fetch property list on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/properties/`);
        if (!res.ok) return;
        const data = await res.json();
        const list: PropertyOption[] = (data.properties ?? data ?? []).map(
          (p: Record<string, unknown>) => ({
            id: p.id as string,
            address: (p.address_jp as string) || (p.address as string) || (p.id as string),
            asking_price: Number(p.baibai_kakaku_yen ?? p.asking_price ?? 0),
          })
        );
        setProperties(list);
        if (list.length > 0) setSelectedId(list[0].id);
      } catch {
        /* ignore fetch error on mount */
      }
    })();
  }, []);

  const runSimulation = useCallback(async () => {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/buyer-simulation/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ property_id: selectedId, n_buyers: nBuyers }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail ?? `API error: ${res.status}`);
      }
      const data: BuyerSimResult = await res.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }, [selectedId, nBuyers]);

  // ---------- Derived chart data ----------

  const priceComparisonData = result
    ? [
        { name: "GNN評価", value: result.gnn_valuation_yen },
        ...(result.satei_price_yen
          ? [{ name: "査定価格", value: result.satei_price_yen }]
          : []),
        ...(result.price_probability_sweet_spot_yen
          ? [{ name: "最適売出価格", value: result.price_probability_sweet_spot_yen }]
          : []),
        { name: "入札中央値", value: result.median_bid_yen },
      ]
    : [];

  const segmentPieData = result
    ? result.buyer_segments.map((s) => ({
        name: LIFE_STAGE_LABELS[s.life_stage] || s.life_stage,
        value: s.count,
      }))
    : [];

  const histogramData = result
    ? result.bid_histogram.map((b) => ({
        range: `${formatYen(b.low_yen)}~`,
        count: b.count,
      }))
    : [];

  // ---------- Styles ----------

  const card: React.CSSProperties = {
    background: "#1e1e2e",
    border: "1px solid #313244",
    borderRadius: 8,
    padding: 20,
    marginBottom: 16,
  };

  const label: React.CSSProperties = {
    fontSize: 12,
    color: "#a6adc8",
    marginBottom: 4,
    display: "block",
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24, color: "#cdd6f4" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>
        バイヤーシミュレーション
      </h1>
      <p style={{ color: "#a6adc8", marginBottom: 24 }}>
        GNN Buyer Simulation — AI-powered demand analysis for listing strategy
      </p>

      {/* Controls */}
      <div style={{ ...card, display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 300px" }}>
          <span style={label}>物件を選択</span>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            style={{
              width: "100%",
              padding: 8,
              borderRadius: 4,
              border: "1px solid #45475a",
              background: "#181825",
              color: "#cdd6f4",
            }}
          >
            {properties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.address} ({formatYen(p.asking_price)})
              </option>
            ))}
          </select>
        </div>

        <div style={{ flex: "0 0 120px" }}>
          <span style={label}>買い手数</span>
          <input
            type="number"
            min={10}
            max={200}
            value={nBuyers}
            onChange={(e) => setNBuyers(Number(e.target.value))}
            style={{
              width: "100%",
              padding: 8,
              borderRadius: 4,
              border: "1px solid #45475a",
              background: "#181825",
              color: "#cdd6f4",
            }}
          />
        </div>

        <button
          onClick={runSimulation}
          disabled={loading || !selectedId}
          style={{
            padding: "10px 24px",
            borderRadius: 4,
            border: "none",
            background: loading ? "#45475a" : "#6366f1",
            color: "#fff",
            fontWeight: 600,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "実行中..." : "シミュレーション実行"}
        </button>
      </div>

      {error && (
        <div
          style={{
            ...card,
            background: "#302020",
            border: "1px solid #f38ba8",
            color: "#f38ba8",
          }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* KPI Row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 12,
              marginBottom: 16,
            }}
          >
            <div style={card}>
              <span style={label}>GNN評価額</span>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#6366f1" }}>
                {formatYen(result.gnn_valuation_yen)}
              </div>
              <div style={{ fontSize: 11, color: "#a6adc8", marginTop: 4 }}>
                {formatYen(result.gnn_confidence_low_yen)} ~ {formatYen(result.gnn_confidence_high_yen)}
              </div>
            </div>

            <div style={card}>
              <span style={label}>入札中央値</span>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#22d3ee" }}>
                {formatYen(result.median_bid_yen)}
              </div>
              <div style={{ fontSize: 11, color: "#a6adc8", marginTop: 4 }}>
                平均: {formatYen(result.mean_bid_yen)}
              </div>
            </div>

            <div style={card}>
              <span style={label}>ハザード影響</span>
              <div
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color:
                    result.hazard_impact_pct < -3
                      ? "#f38ba8"
                      : result.hazard_impact_pct > 3
                        ? "#a6e3a1"
                        : "#cdd6f4",
                }}
              >
                {result.hazard_impact_pct >= 0 ? "+" : ""}
                {result.hazard_impact_pct.toFixed(1)}%
              </div>
            </div>

            <div style={card}>
              <span style={label}>収束ラウンド</span>
              <div style={{ fontSize: 20, fontWeight: 700 }}>
                {result.rounds_to_converge}
              </div>
            </div>
          </div>

          {/* Charts Row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {/* Price comparison bar chart */}
            <div style={card}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
                価格比較
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={priceComparisonData} layout="vertical">
                  <XAxis
                    type="number"
                    tickFormatter={(v: number) => formatYen(v)}
                    stroke="#585b70"
                  />
                  <YAxis type="category" dataKey="name" width={100} stroke="#585b70" />
                  <Tooltip
                    formatter={(v: number) => formatYen(v)}
                    contentStyle={{ background: "#1e1e2e", border: "1px solid #313244" }}
                  />
                  <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Buyer segments pie chart */}
            <div style={card}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
                買い手セグメント
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={segmentPieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={(entry: { name: string; value: number }) =>
                      `${entry.name} (${entry.value})`
                    }
                  >
                    {segmentPieData.map((_, i) => (
                      <Cell
                        key={`seg-${i}`}
                        fill={SEGMENT_COLORS[i % SEGMENT_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#1e1e2e", border: "1px solid #313244" }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Bid histogram */}
          <div style={card}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
              入札価格分布
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={histogramData}>
                <XAxis dataKey="range" stroke="#585b70" tick={{ fontSize: 11 }} />
                <YAxis stroke="#585b70" />
                <Tooltip
                  contentStyle={{ background: "#1e1e2e", border: "1px solid #313244" }}
                />
                <Bar dataKey="count" fill="#22d3ee" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Segment detail table */}
          <div style={card}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
              セグメント詳細
            </h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #313244" }}>
                  <th style={{ textAlign: "left", padding: 8 }}>セグメント</th>
                  <th style={{ textAlign: "right", padding: 8 }}>人数</th>
                  <th style={{ textAlign: "right", padding: 8 }}>平均入札</th>
                  <th style={{ textAlign: "right", padding: 8 }}>中央値入札</th>
                  <th style={{ textAlign: "right", padding: 8 }}>落札率</th>
                </tr>
              </thead>
              <tbody>
                {result.buyer_segments.map((seg) => (
                  <tr
                    key={seg.life_stage}
                    style={{ borderBottom: "1px solid #313244" }}
                  >
                    <td style={{ padding: 8 }}>
                      {LIFE_STAGE_LABELS[seg.life_stage] || seg.life_stage}
                    </td>
                    <td style={{ textAlign: "right", padding: 8 }}>{seg.count}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>
                      {formatYen(seg.avg_bid_yen)}
                    </td>
                    <td style={{ textAlign: "right", padding: 8 }}>
                      {formatYen(seg.median_bid_yen)}
                    </td>
                    <td style={{ textAlign: "right", padding: 8 }}>
                      {(seg.win_rate * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Narrative */}
          <div style={card}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
              分析レポート
            </h3>
            <div
              style={{
                whiteSpace: "pre-wrap",
                lineHeight: 1.8,
                fontSize: 14,
                color: "#bac2de",
              }}
            >
              {result.narrative_jp}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
