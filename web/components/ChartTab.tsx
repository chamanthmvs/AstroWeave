"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ChartSummary } from "@/lib/types";

type Profile = {
  summary?: { rasi?: string; nakshatra?: string; lagna?: string };
  nakshatra?: Record<string, string>;
  rasi?: Record<string, string>;
  lagna?: Record<string, string>;
  in_simple_terms?: string[];
  note?: string;
};

export default function ChartTab() {
  const [chart, setChart] = useState<ChartSummary | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<ChartSummary>("/me/chart"),
      api<Profile>("/me/profile"),
    ])
      .then(([c, p]) => {
        setChart(c);
        setProfile(p);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="stack">
      <div className="hero">
        <div className="eyebrow">Your classical profile</div>
        <h1>My Chart</h1>
        <p>Your Moon sign, birth star and rising sign — the facts first, then the same thing in plain words.</p>
      </div>

      {loading && <p className="muted center">Computing your chart…</p>}
      {error && <p className="error">{error}</p>}

      {chart && (
        <div className="facts">
          <Fact k="Rasi (Moon sign)" v={chart.rasi} />
          <Fact k="Nakshatra" v={chart.nakshatra} />
          <Fact k="Lagna (Rising)" v={chart.lagna} />
          <Fact k="Sun sign" v={chart.sun_sign} />
        </div>
      )}

      {profile?.nakshatra && (
        <div className="card">
          <div className="section-title">Birth star</div>
          <div className="nak-attrs" style={{ marginTop: 12 }}>
            {attrRows(profile.nakshatra, ["ruling_planet", "deity", "gana", "yoni", "nadi"])}
          </div>
        </div>
      )}

      {(profile?.rasi || profile?.lagna) && (
        <div className="row-2">
          {profile?.rasi && (
            <div className="card">
              <div className="section-title">Moon sign</div>
              <div className="nak-attrs" style={{ marginTop: 12 }}>
                {attrRows(profile.rasi, ["element", "modality", "varna"])}
              </div>
            </div>
          )}
          {profile?.lagna && (
            <div className="card">
              <div className="section-title">Rising sign</div>
              <div className="nak-attrs" style={{ marginTop: 12 }}>
                {attrRows(profile.lagna, ["sign", "lord", "element", "modality"])}
              </div>
            </div>
          )}
        </div>
      )}

      {profile?.in_simple_terms && profile.in_simple_terms.length > 0 && (
        <div className="card">
          <div className="section-title">In plain words</div>
          <ul style={{ margin: "12px 0 0", paddingLeft: 18 }} className="dim">
            {profile.in_simple_terms.map((line, i) => (
              <li key={i} style={{ marginBottom: 8 }}>
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}

      {profile?.note && <p className="note center">{profile.note}</p>}
    </section>
  );
}

function Fact({ k, v }: { k: string; v?: string | null }) {
  return (
    <div className="fact">
      <div className="k">{k}</div>
      <div className="v">{v || "—"}</div>
    </div>
  );
}

function attrRows(obj: Record<string, string>, keys: string[]) {
  return keys
    .filter((key) => obj[key])
    .map((key) => (
      <div key={key}>
        <span>{key.replace(/_/g, " ")}</span>
        <b>{obj[key]}</b>
      </div>
    ));
}
