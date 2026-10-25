"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Num = { number: number; meaning: string; about: string };
type Numerology = { name_used: string; method: string; numbers: Record<string, Num> };

const FEATURED: { key: string; label: string }[] = [
  { key: "life_path", label: "Life Path" },
  { key: "personal_year", label: "Personal Year" },
];
const OTHERS: { key: string; label: string }[] = [
  { key: "expression", label: "Expression" },
  { key: "soul_urge", label: "Soul Urge" },
  { key: "personality", label: "Personality" },
  { key: "maturity", label: "Maturity" },
  { key: "birthday", label: "Birthday" },
];

export default function NumerologyTab() {
  const [data, setData] = useState<Numerology | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<Numerology>("/me/numerology"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load your numerology.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="stack">
      <div className="hero">
        <div className="eyebrow">Numerology</div>
        <h1>Your numbers</h1>
        <p>
          Core numbers from your name and birth date, by the classical Pythagorean method. Instant and always
          available — no chart needed.
        </p>
      </div>

      {loading && <p className="muted center">Calculating your numbers…</p>}
      {error && !loading && (
        <div className="card center stack">
          <p className="dim">{error}</p>
          <button className="btn btn-primary" onClick={load} style={{ margin: "0 auto" }}>Try again</button>
        </div>
      )}

      {data && (
        <>
          <div className="row-2">
            {FEATURED.filter((l) => data.numbers[l.key]).map((l) => {
              const n = data.numbers[l.key];
              return (
                <article key={l.key} className="card card-glow num-feature">
                  <div className="eyebrow">{l.label}</div>
                  <div className="num-big">{n.number}</div>
                  <div className="num-headline">{n.meaning.split(" — ")[0]}</div>
                  <p className="dim" style={{ marginTop: 6 }}>
                    {n.meaning.includes(" — ") ? n.meaning.split(" — ")[1] : n.meaning}
                  </p>
                  <p className="note" style={{ marginTop: 8 }}>{n.about}</p>
                </article>
              );
            })}
          </div>

          <div className="atlas-grid" style={{ marginTop: 16 }}>
            {OTHERS.filter((l) => data.numbers[l.key]).map((l) => {
              const n = data.numbers[l.key];
              return (
                <article key={l.key} className="card nak-card">
                  <span className="num">{n.number}</span>
                  <div className="nak-name">{l.label}</div>
                  <div className="nak-south">{n.meaning.split(" — ")[0]}</div>
                  <p className="nak-theme">{n.meaning.includes(" — ") ? n.meaning.split(" — ")[1] : n.meaning}</p>
                  <p className="note">{n.about}</p>
                </article>
              );
            })}
          </div>
        </>
      )}

      {data && (
        <p className="note center" style={{ marginTop: 20 }}>
          This is a generic reading by the standard Pythagorean method. Numerology is a traditional system, not
          a science — take it as reflection, not fact. For a personal reading, consult a professional numerologist.
        </p>
      )}
    </section>
  );
}
