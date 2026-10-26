"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { MatchReading, ReadingSection } from "@/lib/types";
import BirthFields, { emptyBirth, isGeocoded, type BirthForm } from "./BirthFields";

type Koota = { koota: string; score: number; max: number; favourable: boolean };
type Porutham = { porutham: string; matched: boolean };
type MatchResult = {
  north: { total: number; out_of: number; kootas: Koota[]; nadi_dosha: boolean; bhakoot_dosha: boolean };
  south: { matched_count: number; out_of: number; poruthams: Porutham[]; minimum_poruthams_met: boolean };
  manglik: { person: { is_manglik: boolean }; partner: { is_manglik: boolean }; both_manglik: boolean };
};

const KOOTA_MEANING: Record<string, string> = {
  Varna: "spiritual compatibility and work/ego nature",
  Vasya: "mutual attraction and influence",
  Gana: "temperament — Deva, Manushya or Rakshasa",
  Tara: "health and fortune, from the birth stars",
  Yoni: "instinctive and physical compatibility",
  "Graha Maitri": "mental rapport, via the sign lords",
  Bhakoot: "emotional bond and family welfare (Moon signs)",
  Nadi: "health and constitution (genetic compatibility)",
};
const PORUTHAM_MEANING: Record<string, string> = {
  Dina: "day-to-day health and well-being",
  Gana: "temperament match",
  Mahendra: "progeny and a lasting bond",
  "Stree Dheerga": "the bride's welfare and marriage longevity",
  Yoni: "physical compatibility",
  Rasi: "emotional harmony (Moon signs)",
  Rasyadhipathi: "friendship of the sign lords",
  Vasya: "mutual attraction",
  Rajju: "longevity of the marriage",
  Vedha: "freedom from affliction between the stars",
};

function interpret(total: number, outOf: number): string {
  const pct = total / outOf;
  if (pct < 0.5) return "Below the traditional threshold — not recommended on points alone.";
  if (pct < 0.68) return "Acceptable — an average match on points.";
  if (pct < 0.9) return "Very good — a strong match on points.";
  return "Excellent — a very strong match on points.";
}

export default function MatchTab() {
  const { user, readingsEnabled } = useAuth();
  const gender = (user?.gender || "").toLowerCase();
  const autoRole: "groom" | "bride" | null = gender === "male" ? "groom" : gender === "female" ? "bride" : null;

  const [birth, setBirth] = useState<BirthForm>(emptyBirth);
  const [role, setRole] = useState<"groom" | "bride">("groom");
  const [result, setResult] = useState<MatchResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState<MatchReading | null>(null);
  const [readingBusy, setReadingBusy] = useState(false);
  const [readingError, setReadingError] = useState("");

  const personIsGroom = autoRole ? autoRole === "groom" : role === "groom";
  const partnerIs = personIsGroom ? "bride" : "groom";

  function partnerPayload() {
    return {
      date: birth.date,
      time: birth.time.length === 5 ? `${birth.time}:00` : birth.time,
      latitude: birth.latitude,
      longitude: birth.longitude,
      utc_offset_hours: birth.utc_offset_hours,
      place_name: birth.place,
    };
  }

  async function match(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setReading(null);
    setReadingError("");
    if (!isGeocoded(birth)) {
      setError("Please find the partner's birth place first.");
      return;
    }
    setBusy(true);
    try {
      const res = await api<MatchResult>("/match", {
        method: "POST",
        body: { partner: partnerPayload(), person_is_groom: personIsGroom },
      });
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "The match could not be computed.");
    } finally {
      setBusy(false);
    }
  }

  async function getReading() {
    setReadingError("");
    setReadingBusy(true);
    try {
      const res = await api<{ reading: MatchReading }>("/match/reading", {
        method: "POST",
        timeoutMs: 300000, // the deep reading weighs two full charts — allow a couple of minutes
        body: { partner: partnerPayload(), person_is_groom: personIsGroom },
      });
      setReading(res.reading);
    } catch (err: unknown) {
      setReadingError(err instanceof Error ? err.message : "The reading could not be generated.");
    } finally {
      setReadingBusy(false);
    }
  }

  const pct = result ? Math.round((result.north.total / result.north.out_of) * 100) : 0;

  return (
    <section className="stack">
      <div className="hero">
        <div className="eyebrow">Kundli Milan</div>
        <h1>Match a partner&apos;s chart</h1>
        <p>
          Guna Milan compares the two Moon-nakshatras across eight kootas (36 points in the North system) and
          ten poruthams (South system), and checks Manglik dosha. It&apos;s a time-tested compatibility
          screen — one meaningful input, not a verdict on a relationship.
        </p>
      </div>

      <form className="card card-glow" onSubmit={match}>
        <div className="section-title" style={{ marginBottom: 6 }}>Partner&apos;s birth details</div>
        {autoRole ? (
          <p className="note" style={{ marginBottom: 12 }}>
            Matching <b className="dim">you</b> (the {autoRole}) with your partner (the {partnerIs}).
          </p>
        ) : (
          <label className="field" style={{ maxWidth: 220 }}>
            <span>You are the</span>
            <select value={role} onChange={(e) => setRole(e.target.value as "groom" | "bride")}>
              <option value="groom">Groom</option>
              <option value="bride">Bride</option>
            </select>
          </label>
        )}
        <BirthFields value={birth} onChange={setBirth} />
        <button className="btn btn-primary" disabled={busy} style={{ marginTop: 6 }}>
          {busy ? "Computing…" : "Match charts"}
        </button>
        <p className="error">{error}</p>
      </form>

      {result && (
        <>
          <div className="row-2">
            <div className="card center">
              <div className="eyebrow">Guna Milan (North)</div>
              <div className="score-ring" style={{ "--p": pct } as React.CSSProperties}>
                <div className="inner"><div><b>{result.north.total}</b><div className="note">/ {result.north.out_of}</div></div></div>
              </div>
              <p className="dim" style={{ marginTop: 12 }}>{interpret(result.north.total, result.north.out_of)}</p>
              <p className="note" style={{ marginTop: 6 }}>
                {result.north.nadi_dosha && "Nadi dosha present. "}
                {result.north.bhakoot_dosha && "Bhakoot dosha present. "}
                {!result.north.nadi_dosha && !result.north.bhakoot_dosha && "No Nadi or Bhakoot dosha."}
              </p>
            </div>
            <div className="card center">
              <div className="eyebrow">Dasa Porutham (South)</div>
              <div className="score-ring" style={{ "--p": (result.south.matched_count / result.south.out_of) * 100 } as React.CSSProperties}>
                <div className="inner"><div><b>{result.south.matched_count}</b><div className="note">/ {result.south.out_of}</div></div></div>
              </div>
              <p className="dim" style={{ marginTop: 12 }}>
                {result.south.minimum_poruthams_met ? "Meets the minimum poruthams." : "Below the minimum poruthams."}
              </p>
            </div>
          </div>

          <div className="card">
            <div className="section-title">The eight kootas</div>
            <div className="koota-list">
              {result.north.kootas.map((k) => (
                <div className="koota-row" key={k.koota}>
                  <div>
                    <div className="koota-name">{k.koota}</div>
                    <div className="note">{KOOTA_MEANING[k.koota] || ""}</div>
                  </div>
                  <b style={{ color: k.favourable ? "var(--ok)" : "var(--danger)" }}>{k.score} / {k.max}</b>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="section-title">Poruthams</div>
            <div className="koota-list">
              {result.south.poruthams.map((p) => (
                <div className="koota-row" key={p.porutham}>
                  <div>
                    <div className="koota-name">{p.porutham}</div>
                    <div className="note">{PORUTHAM_MEANING[p.porutham] || ""}</div>
                  </div>
                  <b style={{ color: p.matched ? "var(--ok)" : "var(--danger)" }}>{p.matched ? "Yes" : "No"}</b>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="section-title">Manglik (Mangal dosha)</div>
            <div className="nak-attrs" style={{ marginTop: 12 }}>
              <div><span>You</span><b>{result.manglik.person.is_manglik ? "Manglik" : "Not Manglik"}</b></div>
              <div><span>Partner</span><b>{result.manglik.partner.is_manglik ? "Manglik" : "Not Manglik"}</b></div>
              <div><span>Both</span><b>{result.manglik.both_manglik ? "Both Manglik" : "Not both"}</b></div>
            </div>
          </div>

          <p className="note center">
            These scores are a classical screening from the Moon nakshatras alone. A full reading weighs the
            whole chart — dashas, doshas and the 7th house — so treat this as guidance, not a final answer.
          </p>

          <div className="card card-glow">
            <div className="section-title">In-depth AI compatibility reading</div>
            <p className="dim" style={{ margin: "8px 0 14px" }}>
              A grounded reading of the {partnerIs}&apos;s chart — temperament, family, health, work and
              finances — how they&apos;re likely to care for and respect a partner, and the married-life
              indications from both full charts. Marriage is a life decision, so we treat this seriously:
              it describes tendencies, never a verdict on a person.
            </p>

            {!readingsEnabled ? (
              <p className="note">
                Paused on the free tier — the full charts this reading needs aren&apos;t computed on free
                hosting. It runs on the full version; we&apos;ll switch it on once we&apos;re funded.
              </p>
            ) : !user?.match_access ? (
              <p className="note">
                This reading is unlocked individually. Ask an admin to enable it for your account, and
                you&apos;ll get the full compatibility reading.
              </p>
            ) : reading ? (
              <div className="stack" style={{ marginTop: 4 }}>
                <ReadingBlock title="Overview" body={reading.partner_overview} />
                <ReadingBlock title="Temperament & mind" body={reading.partner_temperament} />
                <ReadingBlock title="Family life" body={reading.partner_family} />
                <ReadingBlock title="Health & constitution" body={reading.partner_health} />
                <ReadingBlock title="Work" body={reading.partner_work} />
                <ReadingBlock title="Finances" body={reading.partner_finances} />
                <ReadingBlock title="Care & respect for a partner" body={reading.care_and_respect} />
                <ReadingBlock title="Married life" body={reading.married_life} />
                <ReadingBlock title="In short" body={reading.overall} />
                {reading.limits && (
                  <div>
                    <div className="koota-name">What this can&apos;t tell you</div>
                    <p className="dim" style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>{reading.limits}</p>
                  </div>
                )}
                <p className="note" style={{ marginTop: 4 }}>
                  Confidence: <b className="dim">{reading.confidence}</b>
                  {reading.confidence_reason ? ` — ${reading.confidence_reason}` : ""}
                </p>
                <button className="btn-link" onClick={getReading} disabled={readingBusy} style={{ marginTop: 2 }}>
                  {readingBusy ? "Regenerating…" : "Regenerate"}
                </button>
              </div>
            ) : (
              <>
                <button className="btn btn-primary" onClick={getReading} disabled={readingBusy}>
                  {readingBusy ? "Reading both charts… (1–2 min)" : "Generate the in-depth reading"}
                </button>
                <p className="note" style={{ marginTop: 8 }}>
                  Weighs both full charts with the paid model, so it takes a minute or two and counts as one
                  of your daily questions. Please keep this tab open while it works.
                </p>
              </>
            )}
            {readingError && <p className="error">{readingError}</p>}
          </div>
        </>
      )}
    </section>
  );
}

function ReadingBlock({ title, body }: { title: string; body: ReadingSection }) {
  if (!body || (!body.plain && !body.astrology)) return null;
  return (
    <div>
      <div className="koota-name">{title}</div>
      {body.plain && (
        <p className="dim" style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>{body.plain}</p>
      )}
      {body.astrology && (
        <p className="note" style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>
          <b className="dim">Why we see this (astrology): </b>{body.astrology}
        </p>
      )}
    </div>
  );
}
