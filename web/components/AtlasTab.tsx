"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Nakshatra } from "@/lib/types";

export default function AtlasTab() {
  const [list, setList] = useState<Nakshatra[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<{ nakshatras: Nakshatra[] }>("/nakshatras", { auth: false })
      .then((data) => setList(data.nakshatras))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((n) =>
      [n.name, n.south_name, n.deity, n.ruling_planet, n.gana, n.yoni, n.nadi, n.theme, n.symbol]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [list, query]);

  return (
    <section>
      <div className="hero">
        <div className="eyebrow">The 27 Nakshatras</div>
        <h1>Star Atlas</h1>
        <p>
          Every lunar mansion of the sidereal zodiac — its symbol, what it stands for, its North-Indian
          and South-Indian names, and the classical details. All facts, no fortune-telling.
        </p>
      </div>

      <div className="toolbar">
        <input
          placeholder="Search by name, planet, deity, symbol…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search nakshatras"
        />
        <span className="note">
          {loading ? "Loading…" : `${filtered.length} of ${list.length}`}
        </span>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="atlas-grid">
        {filtered.map((n) => (
          <article key={n.number} className="card nak-card">
            <span className="num">{n.number}</span>
            <div className="nak-symbol" aria-hidden>
              {symbolGlyph(n.symbol)}
            </div>
            <div className="nak-name">{n.name}</div>
            <div className="nak-south">South: {n.south_name}</div>
            <p className="nak-theme">{n.theme}</p>
            <div className="nak-attrs">
              <div>
                <span>Symbol</span>
                <b>{n.symbol}</b>
              </div>
              <div>
                <span>Deity</span>
                <b>{n.deity}</b>
              </div>
              <div>
                <span>Ruler</span>
                <b>{n.ruling_planet}</b>
              </div>
              <div>
                <span>Gana</span>
                <b>{n.gana}</b>
              </div>
              <div>
                <span>Yoni</span>
                <b>{n.yoni}</b>
              </div>
              <div>
                <span>Nadi</span>
                <b>{n.nadi}</b>
              </div>
              <div>
                <span>From</span>
                <b>{n.span.start}</b>
              </div>
              <div>
                <span>To</span>
                <b>{n.span.end}</b>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

// A small decorative glyph hinting at the symbol; the exact symbol is also named in text.
function symbolGlyph(symbol: string): string {
  const s = symbol.toLowerCase();
  if (s.includes("horse")) return "🐎";
  if (s.includes("yoni")) return "◡";
  if (s.includes("razor") || s.includes("flame") || s.includes("fire")) return "🔥";
  if (s.includes("cart") || s.includes("chariot")) return "🛒";
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
