"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import BirthFields, { emptyBirth, isGeocoded, type BirthForm } from "./BirthFields";

type Koota = { koota: string; score: number; max: number; favourable: boolean };
type Porutham = { porutham: string; matched: boolean };
type MatchResult = {
  north: { total: number; out_of: number; kootas: Koota[]; nadi_dosha: boolean; bhakoot_dosha: boolean };
  south: { matched_count: number; out_of: number; poruthams: Porutham[]; minimum_poruthams_met: boolean };
  manglik: { person: { is_manglik: boolean }; partner: { is_manglik: boolean }; both_manglik: boolean };
};

export default function MatchTab() {
  const [birth, setBirth] = useState<BirthForm>(emptyBirth);
  const [role, setRole] = useState<"groom" | "bride">("groom");
  const [result, setResult] = useState<MatchResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function match(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!isGeocoded(birth)) {
      setError("Please find the partner's birth place first.");
      return;
    }
    setBusy(true);
    try {
      const res = await api<MatchResult>("/match", {
        method: "POST",
        body: {
          partner: {
            date: birth.date,
            time: birth.time.length === 5 ? `${birth.time}:00` : birth.time,
            latitude: birth.latitude,
            longitude: birth.longitude,
            utc_offset_hours: birth.utc_offset_hours,
            place_name: birth.place,
          },
          person_is_groom: role === "groom",
        },
      });
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "The match could not be computed.");
    } finally {
      setBusy(false);
    }
  }

  const pct = result ? Math.round((result.north.total / result.north.out_of) * 100) : 0;

  return (
    <section className="stack">
      <div className="hero">
        <div className="eyebrow">Kundli Milan</div>
        <h1>Match a partner&apos;s chart</h1>
        <p>
          We compute the North-Indian 36-point Guna Milan and the South-Indian poruthams from both charts.
          The scores are calculated from the nakshatras — not guessed.
        </p>
      </div>

      <form className="card" onSubmit={match}>
        <BirthFields value={birth} onChange={setBirth} />
        <div className="geo-row" style={{ marginTop: 10 }}>
          <label className="field">
            <span>Your role</span>
            <select value={role} onChange={(e) => setRole(e.target.value as "groom" | "bride")}>
              <option value="groom">I am the groom</option>
              <option value="bride">I am the bride</option>
            </select>
          </label>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "…" : "Match charts"}
          </button>
        </div>
        <p className="error">{error}</p>
      </form>

      {result && (
        <>
          <div className="row-2">
            <div className="card center">
              <div className="eyebrow">Guna Milan (North)</div>
              <div className="score-ring" style={{ "--p": pct } as React.CSSProperties}>
                <div className="inner">
                  <div>
                    <b>{result.north.total}</b>
                    <div className="note">/ {result.north.out_of}</div>
                  </div>
                </div>
              </div>
              <p className="note" style={{ marginTop: 12 }}>
                {result.north.nadi_dosha && "Nadi dosha present. "}
                {result.north.bhakoot_dosha && "Bhakoot dosha present. "}
                {!result.north.nadi_dosha && !result.north.bhakoot_dosha && "No Nadi or Bhakoot dosha."}
              </p>
            </div>

            <div className="card center">
              <div className="eyebrow">Dasa Porutham (South)</div>
              <div
                className="score-ring"
                style={{ "--p": (result.south.matched_count / result.south.out_of) * 100 } as React.CSSProperties}
              >
                <div className="inner">
                  <div>
                    <b>{result.south.matched_count}</b>
                    <div className="note">/ {result.south.out_of}</div>
                  </div>
                </div>
              </div>
              <p className="note" style={{ marginTop: 12 }}>
                {result.south.minimum_poruthams_met ? "Minimum poruthams met." : "Minimum poruthams not met."}
              </p>
            </div>
          </div>

          <div className="card">
            <div className="section-title">The eight kootas</div>
            <div className="nak-attrs" style={{ marginTop: 12 }}>
              {result.north.kootas.map((k) => (
                <div key={k.koota}>
                  <span>{k.koota}</span>
                  <b style={{ color: k.favourable ? "var(--ok)" : "var(--danger)" }}>
                    {k.score} / {k.max}
                  </b>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="section-title">Poruthams</div>
            <div className="nak-attrs" style={{ marginTop: 12 }}>
              {result.south.poruthams.map((p) => (
                <div key={p.porutham}>
                  <span>{p.porutham}</span>
                  <b style={{ color: p.matched ? "var(--ok)" : "var(--danger)" }}>{p.matched ? "Yes" : "No"}</b>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="section-title">Manglik (Mangal dosha)</div>
            <div className="nak-attrs" style={{ marginTop: 12 }}>
              <div>
                <span>You</span>
                <b>{result.manglik.person.is_manglik ? "Manglik" : "Not Manglik"}</b>
              </div>
              <div>
                <span>Partner</span>
                <b>{result.manglik.partner.is_manglik ? "Manglik" : "Not Manglik"}</b>
              </div>
              <div>
                <span>Both</span>
                <b>{result.manglik.both_manglik ? "Both Manglik" : "Not both"}</b>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
