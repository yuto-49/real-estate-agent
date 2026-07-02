import { useState, useCallback } from "react";
import { NegotiationScenarioChart, ConcessionLadderChart } from "../components/charts/SateiCharts";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface ScenarioResponse {
  scenario_label: string;
  opening_price_yen: number;
  rounds: number;
  settlement_price_yen: number | null;
  settled: boolean;
  concession_path: number[];
  zopa_low_yen: number | null;
  zopa_high_yen: number | null;
}

interface CoachingResponse {
  property_address: string | null;
  client_role: string;
  recommended_opening_yen: number;
  concession_ladder: number[];
  walk_away_yen: number;
  zopa_analysis: string;
  scenarios: ScenarioResponse[];
  coaching_notes: string[];
}

export default function NegotiationCoachPage() {
  const [askingPrice, setAskingPrice] = useState<number | "">("");
  const [reservationPrice, setReservationPrice] = useState<number | "">("");
  const [role, setRole] = useState<"seller" | "buyer">("seller");
  const [motivation, setMotivation] = useState("standard");
  const [address, setAddress] = useState("");
  const [counterpartyType, setCounterpartyType] = useState("balanced");
  const [result, setResult] = useState<CoachingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runCoaching = useCallback(async () => {
    if (!askingPrice || !reservationPrice) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/negotiation-coach/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asking_price_yen: askingPrice,
          client: {
            role,
            reservation_price_yen: reservationPrice,
            motivation,
          },
          counterparty: { archetype: counterpartyType },
          property_address: address || null,
          num_scenarios: 3,
          max_rounds: 8,
        }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data: CoachingResponse = await res.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [askingPrice, reservationPrice, role, motivation, address, counterpartyType]);

  const formatYen = (yen: number) =>
    yen >= 10000
      ? `¥${(yen / 10000).toLocaleString("ja-JP", { maximumFractionDigits: 0 })}万`
      : `¥${yen.toLocaleString("ja-JP")}`;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>
        交渉戦略コーチ
      </h1>
      <p style={{ color: "#666", marginBottom: 24 }}>
        Negotiation Strategy Coach — rehearse scenarios before real negotiations
      </p>

      {/* Input Form */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
        gap: 12, marginBottom: 16, padding: 16, border: "1px solid #e0e0e0", borderRadius: 8, background: "#fafafa",
      }}>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Your Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value as "seller" | "buyer")}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}>
            <option value="seller">Seller (売主側)</option>
            <option value="buyer">Buyer (買主側)</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Asking Price (円)</label>
          <input type="number" placeholder="e.g. 50000000" value={askingPrice}
            onChange={(e) => setAskingPrice(e.target.value ? Number(e.target.value) : "")}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Reservation Price (円)</label>
          <input type="number" placeholder="Walk-away price" value={reservationPrice}
            onChange={(e) => setReservationPrice(e.target.value ? Number(e.target.value) : "")}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Client Motivation</label>
          <select value={motivation} onChange={(e) => setMotivation(e.target.value)}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}>
            <option value="standard">Standard</option>
            <option value="urgent">Urgent (急ぎ)</option>
            <option value="patient">Patient (余裕あり)</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Counterparty Type</label>
          <select value={counterpartyType} onChange={(e) => setCounterpartyType(e.target.value)}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }}>
            <option value="conservative">Conservative</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, color: "#555" }}>Property Address</label>
          <input type="text" placeholder="物件住所 (optional)" value={address}
            onChange={(e) => setAddress(e.target.value)}
            style={{ width: "100%", padding: 8, borderRadius: 4, border: "1px solid #ccc" }} />
        </div>
      </div>

      <button onClick={runCoaching} disabled={loading || !askingPrice || !reservationPrice}
        style={{ padding: "10px 24px", background: loading ? "#ccc" : "#7c3aed", color: "#fff",
          border: "none", borderRadius: 6, fontWeight: 600, cursor: loading ? "wait" : "pointer", marginBottom: 24 }}>
        {loading ? "Simulating..." : "Run Coaching Session"}
      </button>

      {error && (
        <div style={{ padding: 12, background: "#fef2f2", color: "#dc2626", borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {result && (
        <>
          {/* Summary Strip */}
          <div style={{ display: "flex", gap: 24, padding: 20, background: "#f5f3ff", borderRadius: 8, marginBottom: 24, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 12, color: "#555" }}>Recommended Opening</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#7c3aed" }}>{formatYen(result.recommended_opening_yen)}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#555" }}>Walk-Away</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: "#dc2626" }}>{formatYen(result.walk_away_yen)}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#555" }}>Scenarios Settled</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{result.scenarios.filter((s) => s.settled).length}/{result.scenarios.length}</div>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 12, color: "#555" }}>ZOPA Analysis</div>
              <div style={{ fontSize: 13 }}>{result.zopa_analysis}</div>
            </div>
          </div>

          {/* Charts */}
          <NegotiationScenarioChart
            scenarios={result.scenarios}
            askingPrice={typeof askingPrice === "number" ? askingPrice : 0}
            reservationPrice={typeof reservationPrice === "number" ? reservationPrice : 0}
          />

          <ConcessionLadderChart
            ladder={result.concession_ladder}
            askingPrice={typeof askingPrice === "number" ? askingPrice : 0}
            walkAwayPrice={result.walk_away_yen}
            clientRole={result.client_role}
          />

          {/* Coaching Notes */}
          {result.coaching_notes.length > 0 && (
            <div style={{ padding: 16, background: "#fffbeb", border: "1px solid #fbbf24", borderRadius: 8, marginTop: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: "#92400e" }}>Coaching Notes</h3>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {result.coaching_notes.map((note, i) => (
                  <li key={i} style={{ fontSize: 13, marginBottom: 4 }}>{note}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {!result && !loading && (
        <div style={{ textAlign: "center", padding: 48, color: "#999" }}>
          <p style={{ fontSize: 16 }}>Enter negotiation parameters and click Run Coaching Session.</p>
          <p style={{ fontSize: 13 }}>The system will simulate 3 counterparty scenarios and produce strategy recommendations.</p>
        </div>
      )}
    </div>
  );
}
