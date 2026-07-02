import { useState, useCallback } from "react";
import { CompPriceChart, PriceProbabilityCurveChart, DaysOnMarketChart } from "../components/charts/SateiCharts";

// Types
interface AdjustmentDetail {
  factor_name: string;
  comp_value: number | string | null;
  subject_value: number | string | null;
  adjustment_pct: number;
}

interface AdjustedComp {
  comp_id: string;
  address_hint: string | null;
  raw_price_yen: number;
  adjusted_price_yen: number;
  menseki_m2: number | null;
  built_year: number | null;
  construction_type: string | null;
  walk_minutes: number | null;
  transaction_year: number | null;
  transaction_quarter: number | null;
  adjustments: AdjustmentDetail[];
  total_adjustment_pct: number;
}

interface SateiResult {
  session_id: string | null;
  satei_price_yen: number;
  confidence_low_yen: number;
  confidence_high_yen: number;
  comp_count: number;
  comps: AdjustedComp[];
  method: string;
}

interface PriceProbabilityPoint {
  asking_price_yen: number;
  premium_pct: number;
  p30: number;
  p60: number;
  p90: number;
  p180: number;
  expected_days: number;
  expected_settlement_yen: number;
}

interface PriceCurveResult {
  satei_price_yen: number;
  points: PriceProbabilityPoint[];
  iterations_per_point: number;
  sweet_spot_yen: number | null;
  sweet_spot_pct: number | null;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function SateiPage() {
  const [tab, setTab] = useState<"grid" | "curve">("grid");

  // Input state
  const [cityCode, setCityCode] = useState("");
  const [address, setAddress] = useState("");
  const [menseki, setMenseki] = useState<number | "">("");
  const [builtYear, setBuiltYear] = useState<number | "">("");
  const [constructionType, setConstructionType] = useState("");
  const [walkMinutes, setWalkMinutes] = useState<number | "">("");

  // Result state
  const [sateiResult, setSateiResult] = useState<SateiResult | null>(null);
  const [curveResult, setCurveResult] = useState<PriceCurveResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [curveLoading, setCurveLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Adjustment overrides (comp_id -> { factor_name: override_pct })
  const [overrides, setOverrides] = useState<Record<string, Record<string, number>>>({});

  const computeSatei = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/satei/compute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city_code: cityCode || null,
          address: address || null,
          menseki_m2: menseki || null,
          built_year: builtYear || null,
          construction_type: constructionType || null,
          walk_minutes: walkMinutes || null,
          overrides: Object.keys(overrides).length > 0 ? overrides : null,
        }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data: SateiResult = await res.json();
      setSateiResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }, [cityCode, address, menseki, builtYear, constructionType, walkMinutes, overrides]);

  const computeCurve = useCallback(async () => {
    if (!sateiResult || sateiResult.satei_price_yen <= 0) return;
    setCurveLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/price-probability/compute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          satei_price_yen: sateiResult.satei_price_yen,
        }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data: PriceCurveResult = await res.json();
      setCurveResult(data);
      setTab("curve");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setCurveLoading(false);
    }
  }, [sateiResult]);

  const handleAdjustmentChange = (compId: string, factor: string, value: string) => {
    const num = parseFloat(value);
    if (isNaN(num)) return;
    setOverrides((prev) => ({
      ...prev,
      [compId]: { ...(prev[compId] || {}), [factor]: num },
    }));
  };

  const formatYen = (yen: number) =>
    yen >= 10000
      ? `\u00A5${(yen / 10000).toLocaleString("ja-JP", { maximumFractionDigits: 0 })}\u4E07`
      : `\u00A5${yen.toLocaleString("ja-JP")}`;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>
        査定コンプグリッド
      </h1>
      <p style={{ color: "#666", marginBottom: 24 }}>
        Satei Comp Grid — AI-powered comparable valuation for listing pitches
      </p>

      {/* Property Input Form */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: 12,
          marginBottom: 16,
          padding: 16,
          border: "1px solid #e0e0e0",
          borderRadius: 8,
          background: "#fafafa",
        }}
      >
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>City Code (市区町村コード)</label>
          <input
            type="text"
            placeholder="e.g. 13101"
            value={cityCode}
            onChange={(e) => setCityCode(e.target.value)}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}
          />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Address</label>
          <input
            type="text"
            placeholder="物件住所"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}
          />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Floor Area (m²)</label>
          <input
            type="number"
            placeholder="専有面積"
            value={menseki}
            onChange={(e) => setMenseki(e.target.value ? Number(e.target.value) : "")}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}
          />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Built Year (築年)</label>
          <input
            type="number"
            placeholder="e.g. 2005"
            value={builtYear}
            onChange={(e) => setBuiltYear(e.target.value ? Number(e.target.value) : "")}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}
          />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Construction (構造)</label>
          <select
            value={constructionType}
            onChange={(e) => setConstructionType(e.target.value)}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}
          >
            <option value="">--</option>
            <option value="木造">木造</option>
            <option value="軽量鉄骨">軽量鉄骨</option>
            <option value="鉄骨">鉄骨</option>
            <option value="RC">RC</option>
            <option value="SRC">SRC</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Walk to Station (min)</label>
          <input
            type="number"
            placeholder="駅徒歩(分)"
            value={walkMinutes}
            onChange={(e) => setWalkMinutes(e.target.value ? Number(e.target.value) : "")}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}
          />
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <button
          onClick={computeSatei}
          disabled={loading || !cityCode}
          style={{
            padding: "10px 24px",
            background: loading ? "#ccc" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            fontWeight: 600,
            cursor: loading ? "wait" : "pointer",
          }}
        >
          {loading ? "Computing..." : "査定を実行"}
        </button>
        {sateiResult && sateiResult.satei_price_yen > 0 && (
          <button
            onClick={computeCurve}
            disabled={curveLoading}
            style={{
              padding: "10px 24px",
              background: curveLoading ? "#ccc" : "#059669",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              fontWeight: 600,
              cursor: curveLoading ? "wait" : "pointer",
            }}
          >
            {curveLoading ? "Computing..." : "価格カーブを生成"}
          </button>
        )}
      </div>

      {error && (
        <div style={{ padding: 12, background: "#fef2f2", color: "#dc2626", borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Satei Result Summary */}
      {sateiResult && sateiResult.satei_price_yen > 0 && (
        <div
          style={{
            padding: 20,
            background: "#eff6ff",
            borderRadius: 8,
            marginBottom: 24,
            display: "flex",
            gap: 32,
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ fontSize: 12, color: "#555" }}>査定価格</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#1e40af" }}>
              {formatYen(sateiResult.satei_price_yen)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: "#555" }}>信頼区間</div>
            <div style={{ fontSize: 16 }}>
              {formatYen(sateiResult.confidence_low_yen)} — {formatYen(sateiResult.confidence_high_yen)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: "#555" }}>Comps Used</div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>{sateiResult.comp_count}</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      {sateiResult && (
        <div style={{ display: "flex", gap: 0, marginBottom: 16, borderBottom: "2px solid #e0e0e0" }}>
          <button
            onClick={() => setTab("grid")}
            style={{
              padding: "10px 20px",
              border: "none",
              borderBottom: tab === "grid" ? "2px solid #2563eb" : "2px solid transparent",
              background: "transparent",
              fontWeight: tab === "grid" ? 700 : 400,
              color: tab === "grid" ? "#2563eb" : "#666",
              cursor: "pointer",
            }}
          >
            Comp Grid (コンプ一覧)
          </button>
          <button
            onClick={() => setTab("curve")}
            style={{
              padding: "10px 20px",
              border: "none",
              borderBottom: tab === "curve" ? "2px solid #059669" : "2px solid transparent",
              background: "transparent",
              fontWeight: tab === "curve" ? 700 : 400,
              color: tab === "curve" ? "#059669" : "#666",
              cursor: "pointer",
            }}
          >
            Price Curve (価格カーブ)
          </button>
        </div>
      )}

      {/* Comp Grid Tab */}
      {tab === "grid" && sateiResult && sateiResult.comps.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f1f5f9" }}>
                <th style={{ padding: 8, textAlign: "left", borderBottom: "1px solid #e0e0e0" }}>Address</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>Raw Price</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>m²</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>Built</th>
                <th style={{ padding: 8, textAlign: "center", borderBottom: "1px solid #e0e0e0" }}>Construction</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>Walk</th>
                {["age", "area", "walk", "construction"].map((f) => (
                  <th
                    key={f}
                    style={{
                      padding: 8,
                      textAlign: "right",
                      borderBottom: "1px solid #e0e0e0",
                      background: "#e8f5e9",
                      fontSize: 11,
                    }}
                  >
                    Adj: {f} (%)
                  </th>
                ))}
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0", fontWeight: 700 }}>
                  Total Adj %
                </th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0", fontWeight: 700 }}>
                  Adjusted Price
                </th>
              </tr>
            </thead>
            <tbody>
              {sateiResult.comps.map((comp) => (
                <tr key={comp.comp_id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                  <td style={{ padding: 8, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {comp.address_hint || "\u2014"}
                  </td>
                  <td style={{ padding: 8, textAlign: "right" }}>{formatYen(comp.raw_price_yen)}</td>
                  <td style={{ padding: 8, textAlign: "right" }}>{comp.menseki_m2?.toFixed(1) || "\u2014"}</td>
                  <td style={{ padding: 8, textAlign: "right" }}>{comp.built_year || "\u2014"}</td>
                  <td style={{ padding: 8, textAlign: "center" }}>{comp.construction_type || "\u2014"}</td>
                  <td style={{ padding: 8, textAlign: "right" }}>{comp.walk_minutes ?? "\u2014"}</td>
                  {["age", "area", "walk", "construction"].map((factor) => {
                    const adj = comp.adjustments.find((a) => a.factor_name === factor);
                    const val = overrides[comp.comp_id]?.[factor] ?? adj?.adjustment_pct ?? 0;
                    return (
                      <td key={factor} style={{ padding: 4, textAlign: "right", background: "#f9fdf9" }}>
                        <input
                          type="number"
                          step="0.5"
                          value={val}
                          onChange={(e) => handleAdjustmentChange(comp.comp_id, factor, e.target.value)}
                          style={{
                            width: 60,
                            textAlign: "right",
                            padding: 4,
                            border: "1px solid #ccc",
                            borderRadius: 3,
                            fontSize: 12,
                          }}
                        />
                      </td>
                    );
                  })}
                  <td
                    style={{
                      padding: 8,
                      textAlign: "right",
                      fontWeight: 600,
                      color: comp.total_adjustment_pct >= 0 ? "#059669" : "#dc2626",
                    }}
                  >
                    {comp.total_adjustment_pct >= 0 ? "+" : ""}
                    {comp.total_adjustment_pct.toFixed(1)}%
                  </td>
                  <td style={{ padding: 8, textAlign: "right", fontWeight: 700 }}>
                    {formatYen(comp.adjusted_price_yen)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {sateiResult && sateiResult.comps.length > 0 && (
            <CompPriceChart
              comps={sateiResult.comps.map((c) => ({
                address: c.address_hint || `Comp ${c.comp_id.slice(0, 6)}`,
                raw_price: c.raw_price_yen,
                adjusted_price: c.adjusted_price_yen,
                adjustment_pct: c.total_adjustment_pct,
              }))}
              sateiPrice={sateiResult.satei_price_yen}
            />
          )}
          {Object.keys(overrides).length > 0 && (
            <button
              onClick={computeSatei}
              style={{
                marginTop: 12,
                padding: "8px 16px",
                background: "#f59e0b",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Recompute with overrides
            </button>
          )}
        </div>
      )}

      {/* Price Curve Tab */}
      {tab === "curve" && curveResult && (
        <div>
          {curveResult.sweet_spot_yen && (
            <div
              style={{
                padding: 16,
                background: "#ecfdf5",
                borderRadius: 8,
                marginBottom: 16,
                display: "flex",
                gap: 24,
              }}
            >
              <div>
                <div style={{ fontSize: 12, color: "#555" }}>{"Sweet Spot (p90 ≥ 80%)"}</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "#059669" }}>
                  {formatYen(curveResult.sweet_spot_yen)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#555" }}>Premium</div>
                <div style={{ fontSize: 16 }}>
                  {curveResult.sweet_spot_pct != null
                    ? `${curveResult.sweet_spot_pct >= 0 ? "+" : ""}${curveResult.sweet_spot_pct}%`
                    : "\u2014"}
                </div>
              </div>
            </div>
          )}

          <PriceProbabilityCurveChart
            points={curveResult.points}
            sateiPrice={curveResult.satei_price_yen}
            sweetSpotYen={curveResult.sweet_spot_yen}
          />
          <DaysOnMarketChart points={curveResult.points} />

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f1f5f9" }}>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>Asking Price</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>Premium</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>P(30d)</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>P(60d)</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>P(90d)</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>P(180d)</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>Expected Days</th>
                <th style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #e0e0e0" }}>Expected Settlement</th>
              </tr>
            </thead>
            <tbody>
              {curveResult.points.map((pt, i) => {
                const isSweet = curveResult.sweet_spot_yen === pt.asking_price_yen;
                return (
                  <tr
                    key={i}
                    style={{
                      borderBottom: "1px solid #f0f0f0",
                      background: isSweet ? "#ecfdf5" : "transparent",
                      fontWeight: isSweet ? 600 : 400,
                    }}
                  >
                    <td style={{ padding: 8, textAlign: "right" }}>{formatYen(pt.asking_price_yen)}</td>
                    <td style={{ padding: 8, textAlign: "right", color: pt.premium_pct >= 0 ? "#059669" : "#dc2626" }}>
                      {pt.premium_pct >= 0 ? "+" : ""}
                      {pt.premium_pct}%
                    </td>
                    <td style={{ padding: 8, textAlign: "right" }}>{(pt.p30 * 100).toFixed(0)}%</td>
                    <td style={{ padding: 8, textAlign: "right" }}>{(pt.p60 * 100).toFixed(0)}%</td>
                    <td style={{ padding: 8, textAlign: "right" }}>{(pt.p90 * 100).toFixed(0)}%</td>
                    <td style={{ padding: 8, textAlign: "right" }}>{(pt.p180 * 100).toFixed(0)}%</td>
                    <td style={{ padding: 8, textAlign: "right" }}>{pt.expected_days}d</td>
                    <td style={{ padding: 8, textAlign: "right" }}>{formatYen(pt.expected_settlement_yen)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!sateiResult && !loading && (
        <div style={{ textAlign: "center", padding: 48, color: "#999" }}>
          <p style={{ fontSize: 16 }}>Enter property details and click 査定を実行 to begin.</p>
          <p style={{ fontSize: 13 }}>
            The system will pull comparable transactions from REINFOLIB and compute a hedonic-adjusted valuation.
          </p>
        </div>
      )}
    </div>
  );
}
