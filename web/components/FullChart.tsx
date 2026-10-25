"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type Dasha = {
  maha_lord: string; maha_start: string; maha_end: string;
  antardasha_lord: string; antardasha_start: string; antardasha_end: string;
  pratyantardasha_lord: string; pratyantardasha_start: string; pratyantardasha_end: string;
};
type Period = { lord: string; start_date: string; end_date: string | null };
type Yoga = { name: string; description: string; benefits: string };
type Planet = { planet: string; sign: string };
type Varga = { ascendant: { sign: string }; planets: Planet[] };
type FullChartData = {
  current_dasha: Dasha | null;
  mahadasha_timeline: Period[];
  yogas: Yoga[];
  divisional_charts: Record<string, Varga>;
  shadbala: Record<string, { strength_rupas: number; strength_ratio: number }>;
  ashtakavarga: { samudhaya?: Record<string, number> };
};

export default function FullChart() {
  const [data, setData] = useState<FullChartData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showYogas, setShowYogas] = useState(false);
  const [varga, setVarga] = useState("D9");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      // The full chart is computed in the background and cached. Poll until ready.
      for (let i = 0; i < 48; i++) {
        const res = await api<FullChartData & { status: string }>("/me/chart/full", { timeoutMs: 30000 });
        if (res.status === "ready") {
          setData(res);
          setLoading(false);
          return;
        }
        await new Promise((r) => setTimeout(r, 5000));
      }
      setError("Still preparing your chart — please try again in a moment.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load the full chart.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const vargaKeys = useMemo(() => (data ? Object.keys(data.divisional_charts) : []), [data]);
  const maxRupas = useMemo(
    () => (data ? Math.max(1, ...Object.values(data.shadbala).map((s) => s.strength_rupas)) : 1),
    [data],
  );
  const maxBindu = 56; // Sarva ashtakavarga max per sign (theoretical), for bar scale

  if (loading) {
    return (
      <div className="card center">
        <p className="muted">Computing your full chart — divisional charts, dashas, yogas, strengths. The free
          server can take up to a minute the first time; it&apos;s saved afterwards, so it&apos;s instant next time.</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="card center stack">
        <p className="dim">{error}</p>
        <button className="btn btn-primary" onClick={load} style={{ margin: "0 auto" }}>Try again</button>
      </div>
    );
  }
  if (!data) return null;

  const d = data.current_dasha;
  const selected = data.divisional_charts[varga];

  return (
    <div className="stack">
      {d && (
        <div className="card">
          <div className="section-title">Current Vimshottari period</div>
          <div className="nak-attrs" style={{ marginTop: 12 }}>
            <div><span>Mahadasha</span><b>{d.maha_lord} ({d.maha_start} → {d.maha_end})</b></div>
            <div><span>Antardasha</span><b>{d.antardasha_lord} ({d.antardasha_start} → {d.antardasha_end})</b></div>
            <div><span>Pratyantardasha</span><b>{d.pratyantardasha_lord} ({d.pratyantardasha_start} → {d.pratyantardasha_end})</b></div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="section-title">Dasha timeline (Vimshottari)</div>
        <div className="koota-list">
          {data.mahadasha_timeline.map((p, i) => {
            const active = d && p.lord === d.maha_lord && p.start_date === d.maha_start;
            return (
              <div className="koota-row" key={i}>
                <div className="koota-name" style={{ color: active ? "var(--accent-2)" : undefined }}>
                  {p.lord} {active ? "· now" : ""}
                </div>
                <b className="dim">{p.start_date} → {p.end_date || "—"}</b>
              </div>
            );
          })}
        </div>
      </div>

      <div className="card">
        <div className="section-title">Planetary strength (Shadbala)</div>
        <div className="stack" style={{ marginTop: 10 }}>
          {Object.entries(data.shadbala)
            .sort((a, b) => b[1].strength_rupas - a[1].strength_rupas)
            .map(([planet, s]) => (
              <div key={planet}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                  <span>{planet}</span>
                  <b>{s.strength_rupas.toFixed(2)} rupas</b>
                </div>
                <div className="bar"><span style={{ width: `${Math.min(100, (s.strength_rupas / maxRupas) * 100)}%` }} /></div>
              </div>
            ))}
        </div>
      </div>

      {data.ashtakavarga?.samudhaya && (
        <div className="card">
          <div className="section-title">Sarva Ashtakavarga (bindus by sign)</div>
          <div className="nak-attrs" style={{ marginTop: 12 }}>
            {Object.entries(data.ashtakavarga.samudhaya).map(([sign, bindu]) => (
              <div key={sign}>
                <span>{sign}</span>
                <b>{bindu}</b>
              </div>
            ))}
          </div>
        </div>
      )}

      {selected && (
        <div className="card">
          <div className="toolbar" style={{ marginBottom: 6 }}>
            <div className="section-title" style={{ marginRight: "auto" }}>Divisional charts</div>
            <select value={varga} onChange={(e) => setVarga(e.target.value)} style={{ maxWidth: 180 }}>
              {vargaKeys.map((k) => <option key={k} value={k}>{k} {VARGA_NAMES[k] ? `· ${VARGA_NAMES[k]}` : ""}</option>)}
            </select>
          </div>
          <p className="note">Ascendant: <b>{selected.ascendant.sign}</b></p>
          <div className="nak-attrs" style={{ marginTop: 10 }}>
            {selected.planets.map((p) => (
              <div key={p.planet}><span>{p.planet}</span><b>{p.sign}</b></div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="section-title">Yogas ({data.yogas.length})</div>
        <div className="stack" style={{ marginTop: 10 }}>
          {(showYogas ? data.yogas : data.yogas.slice(0, 6)).map((y, i) => (
            <div key={i} style={{ borderTop: i ? "1px solid var(--border)" : undefined, paddingTop: i ? 10 : 0 }}>
              <div className="koota-name">{y.name}</div>
              <p className="note" style={{ marginTop: 2 }}>{y.description}</p>
            </div>
          ))}
        </div>
        {data.yogas.length > 6 && (
          <button className="btn-link" style={{ marginTop: 10 }} onClick={() => setShowYogas((s) => !s)}>
            {showYogas ? "Show fewer" : `Show all ${data.yogas.length} yogas`}
          </button>
        )}
      </div>

      <p className="note center">
        These are the classical computations from your chart. They inform the readings in Ask — and are kept
        factual; interpretation is for the specialists, not fortune-telling.
      </p>
    </div>
  );
}

const VARGA_NAMES: Record<string, string> = {
  D2: "Hora", D3: "Drekkana", D4: "Chaturthamsa", D7: "Saptamsa", D9: "Navamsa",
  D10: "Dasamsa", D12: "Dwadasamsa", D24: "Chaturvimsamsa", D30: "Trimsamsa", D60: "Shashtiamsa",
};
