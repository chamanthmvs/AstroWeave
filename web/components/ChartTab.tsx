"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ChartSummary } from "@/lib/types";
import FullChart from "./FullChart";

type Profile = {
  summary?: { rasi?: string; nakshatra?: string; lagna?: string };
  nakshatra?: Record<string, string>;
  rasi?: Record<string, string>;
  lagna?: Record<string, string>;
  in_simple_terms?: string[];
  note?: string;
};

type Extras = { nakMeaning?: string; nakTheme?: string; rasiKeynote?: string };

export default function ChartTab() {
  const [chart, setChart] = useState<ChartSummary | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [extras, setExtras] = useState<Extras>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showFull, setShowFull] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [c, p, n, r] = await Promise.all([
        api<ChartSummary>("/me/chart"),
        api<Profile>("/me/profile"),
        api<{ nakshatras: { name: string; meaning: string; theme: string }[] }>("/nakshatras", { auth: false }),
        api<{ rasis: { name: string; keynote: string }[] }>("/rasis", { auth: false }),
      ]);
      setChart(c);
      setProfile(p);
      const nakName = (p.summary?.nakshatra || "").split(" (")[0].trim();
      const nak = n.nakshatras.find((x) => x.name === nakName);
      const rasi = r.rasis.find((x) => x.name === p.summary?.rasi);
      setExtras({ nakMeaning: nak?.meaning, nakTheme: nak?.theme, rasiKeynote: rasi?.keynote });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load your chart.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const nakName = (profile?.summary?.nakshatra || "").split(" (")[0].trim();

  return (
    <section className="stack">
      <div className="hero">
        <div className="eyebrow">Your classical profile</div>
        <h1>My Chart</h1>
        <p>Your Moon sign, birth star and rising sign — the facts first, then the same thing in plain words.</p>
      </div>

      {loading && (
        <p className="muted center">
          Computing your chart… the free server can take up to a minute to wake on the first load.
        </p>
      )}
      {error && !loading && (
        <div className="card center stack">
          <p className="dim">{error}</p>
          <button className="btn btn-primary" onClick={load} style={{ margin: "0 auto" }}>Try again</button>
        </div>
      )}

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
          {(extras.nakMeaning || extras.nakTheme) && (
            <p className="dim" style={{ marginTop: 8 }}>
              {nakName && (
                <>
                  Your birth star is <b>{nakName}</b>
                  {extras.nakMeaning ? <>, which means “{extras.nakMeaning}.”</> : "."}{" "}
                </>
              )}
              {extras.nakTheme && (
                <>
                  In classical texts it stands for <b>{extras.nakTheme}</b>.
                </>
              )}
            </p>
          )}
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
              {extras.rasiKeynote && (
                <p className="dim" style={{ marginTop: 8 }}>
                  Your Moon sits in <b>{profile?.summary?.rasi}</b> — classically {extras.rasiKeynote}.
                </p>
              )}
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

      {chart && (
        <div className="card center" style={{ marginTop: 10 }}>
          <div className="section-title">Full chart &amp; detailed analysis</div>
          <p className="dim" style={{ margin: "8px 0 14px" }}>
            Dashas (planetary periods), yogas, divisional charts, planetary strengths and ashtakavarga — the
            deeper layers used for real readings. Computed once and saved.
          </p>
          {!showFull ? (
            <button className="btn btn-primary" onClick={() => setShowFull(true)} style={{ margin: "0 auto" }}>
              Load full chart →
            </button>
          ) : (
            <FullChart />
          )}
        </div>
      )}
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
