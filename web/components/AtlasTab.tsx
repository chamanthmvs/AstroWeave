"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Nakshatra } from "@/lib/types";

type Rasi = {
  number: number;
  name: string;
  sanskrit: string;
  symbol: string;
  lord: string;
  element: string;
  modality: string;
  polarity: string;
  exalted: string | null;
  debilitated: string | null;
  body_part: string;
  keynote: string;
};

const ZODIAC = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"];

export default function AtlasTab() {
  const [view, setView] = useState<"nakshatras" | "signs">("nakshatras");
  const [naks, setNaks] = useState<Nakshatra[]>([]);
  const [rasis, setRasis] = useState<Rasi[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<{ nakshatras: Nakshatra[] }>("/nakshatras", { auth: false }),
      api<{ rasis: Rasi[] }>("/rasis", { auth: false }),
    ])
      .then(([n, r]) => {
        setNaks(n.nakshatras);
        setRasis(r.rasis);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const q = query.trim().toLowerCase();
  const filteredNaks = useMemo(
    () =>
      !q
        ? naks
        : naks.filter((n) =>
            [n.name, n.south_name, n.meaning, n.deity, n.ruling_planet, n.gana, n.yoni, n.nadi, n.theme, n.symbol]
              .join(" ")
              .toLowerCase()
              .includes(q),
          ),
    [naks, q],
  );
  const filteredRasis = useMemo(
    () =>
      !q
        ? rasis
        : rasis.filter((r) =>
            [r.name, r.sanskrit, r.lord, r.element, r.modality, r.polarity, r.keynote, r.body_part]
              .join(" ")
              .toLowerCase()
              .includes(q),
          ),
    [rasis, q],
  );

  const shown = view === "nakshatras" ? filteredNaks.length : filteredRasis.length;
  const total = view === "nakshatras" ? naks.length : rasis.length;

  return (
    <section>
      <div className="hero">
        <div className="eyebrow">Classical reference</div>
        <h1>Celestial Atlas</h1>
        <p>
          The building blocks of a Vedic chart — the 27 nakshatras and the 12 rasis — with their symbols,
          names and classical attributes. All reference facts, no fortune-telling.
        </p>
      </div>

      <div className="tabs" style={{ margin: "0 auto 22px" }}>
        <button className="tab" aria-selected={view === "nakshatras"} onClick={() => setView("nakshatras")}>
          27 Nakshatras
        </button>
        <button className="tab" aria-selected={view === "signs"} onClick={() => setView("signs")}>
          12 Rasis
        </button>
      </div>

      <div className="toolbar">
        <input placeholder={`Search ${view}…`} value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search" />
        <span className="note">{loading ? "Loading…" : `${shown} of ${total}`}</span>
      </div>

      {error && <p className="error">{error}</p>}

      {view === "nakshatras" ? (
        <div className="atlas-grid">
          {filteredNaks.map((n) => (
            <article key={n.number} className="card nak-card">
              <span className="num">{n.number}</span>
              <div className="nak-symbol" aria-hidden>{nakGlyph(n.symbol)}</div>
              <div className="nak-name">{n.name}</div>
              <div className="nak-south">South: {n.south_name}</div>
              <p className="nak-theme"><em>{n.meaning}</em> — {n.theme}</p>
              <div className="nak-attrs">
                <div><span>Symbol</span><b>{n.symbol}</b></div>
                <div><span>Deity</span><b>{n.deity}</b></div>
                <div><span>Ruler</span><b>{n.ruling_planet}</b></div>
                <div><span>Gana</span><b>{n.gana}</b></div>
                <div><span>Yoni</span><b>{n.yoni}</b></div>
                <div><span>Nadi</span><b>{n.nadi}</b></div>
                <div><span>From</span><b>{n.span.start}</b></div>
                <div><span>To</span><b>{n.span.end}</b></div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="atlas-grid">
          {filteredRasis.map((r) => (
            <article key={r.number} className="card nak-card">
              <span className="num">{r.number}</span>
              <div className="nak-symbol" aria-hidden>{ZODIAC[r.number - 1]}</div>
              <div className="nak-name">{r.name}</div>
              <div className="nak-south">{r.sanskrit} · {r.symbol}</div>
              <p className="nak-theme">{r.keynote}</p>
              <div className="nak-attrs">
                <div><span>Lord</span><b>{r.lord}</b></div>
                <div><span>Element</span><b>{r.element}</b></div>
                <div><span>Modality</span><b>{r.modality}</b></div>
                <div><span>Polarity</span><b>{r.polarity}</b></div>
                <div><span>Exalted</span><b>{r.exalted || "—"}</b></div>
                <div><span>Debilitated</span><b>{r.debilitated || "—"}</b></div>
                <div><span>Body</span><b>{r.body_part}</b></div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function nakGlyph(symbol: string): string {
  const s = symbol.toLowerCase();
  if (s.includes("horse")) return "🐎";
  if (s.includes("yoni")) return "◡";
  if (s.includes("razor") || s.includes("flame") || s.includes("fire")) return "🔥";
  if (s.includes("cart") || s.includes("chariot")) return "🛺";
  if (s.includes("deer")) return "🦌";
  if (s.includes("tear") || s.includes("gem")) return "💧";
  if (s.includes("bow")) return "🏹";
  if (s.includes("cow") || s.includes("udder")) return "🐄";
  if (s.includes("serpent")) return "🐍";
  if (s.includes("throne")) return "♜";
  if (s.includes("cot") || s.includes("bed")) return "🛏";
  if (s.includes("hand") || s.includes("fist")) return "✋";
  if (s.includes("jewel") || s.includes("pearl")) return "💎";
  if (s.includes("shoot") || s.includes("coral") || s.includes("lotus")) return "🌱";
  if (s.includes("arch")) return "⛩";
  if (s.includes("earring") || s.includes("umbrella")) return "☂";
  if (s.includes("root")) return "🌿";
  if (s.includes("fan") || s.includes("winnow")) return "🪭";
  if (s.includes("elephant") || s.includes("tusk") || s.includes("plank")) return "🐘";
  if (s.includes("ear") || s.includes("footprint")) return "👣";
  if (s.includes("drum")) return "🥁";
  if (s.includes("circle") || s.includes("flower")) return "◯";
  if (s.includes("fish")) return "🐟";
  return "✧";
}
