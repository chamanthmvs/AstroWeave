"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ChartScope, RunResponse } from "@/lib/types";
import CostPanel, { usd } from "./CostPanel";
import ChartScopeNote from "./ChartScopeNote";

type Msg = { role: "user" | "assistant"; content: string; trace?: string; cost?: number; scope?: ChartScope | null };
type Quota = { used: number; limit: number | null; remaining: number | null };

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function AskTab() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [query, setQuery] = useState("");
  const [methodology, setMethodology] = useState("Let the system decide");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [quotaFull, setQuotaFull] = useState(false);
  const [quota, setQuota] = useState<Quota | null>(null);
  const ids = useRef<{ conversation_id?: string; session_id?: string }>({});

  async function loadQuota() {
    try {
      const u = await api<{ user: Quota }>("/usage");
      setQuota(u.user);
      if (u.user.remaining !== null && u.user.remaining <= 0) setQuotaFull(true);
    } catch {
      /* non-fatal */
    } finally {
      // Nudge the top-bar badge to refresh too.
      if (typeof window !== "undefined") window.dispatchEvent(new Event("astroweave:quota-refresh"));
    }
  }

  useEffect(() => {
    loadQuota();
  }, []);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const text = query.trim();
    if (!text || busy) return;
    setError("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setQuery("");
    setBusy(true);
    try {
      const res = await api<RunResponse>("/run", {
        method: "POST",
        timeoutMs: 180000, // a multi-agent reading can take a while
        body: {
          query: text,
          methodology,
          message_id: uuid(),
          conversation_id: ids.current.conversation_id,
          session_id: ids.current.session_id,
        },
      });
      ids.current = { conversation_id: res.conversation_id, session_id: res.session_id };
      const consulted = (res.execution_trace || [])
        .filter((s) => s.step === "specialist" && s.specialist)
        .map((s) => s.specialist);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer || "No answer was produced.",
          trace: consulted.length ? `Consulted: ${consulted.join(", ")}` : undefined,
          cost: res.cost_usd,
          scope: res.chart_scope,
        },
      ]);
      loadQuota();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 429) {
        setQuotaFull(true);
        setError(err.message);
        loadQuota();
      } else {
        setError(err instanceof Error ? err.message : "The reading could not be completed.");
      }
    } finally {
      setBusy(false);
    }
  }

  const remaining = quota?.remaining;
  const limit = quota?.limit;

  return (
    <section>
      {messages.length === 0 && (
        <div className="hero">
          <div className="eyebrow">Personal reading</div>
          <h1>Make room for the answer.</h1>
          <p>
            Ask one clear question about your career, relationships, finances, or the road ahead. The right
            specialists weigh in, and the signal comes back to you — grounded in your chart, with its limits
            stated plainly.
          </p>
          {limit != null && (
            <div className="usp">
              <span className="pill">
                <b>{remaining ?? limit}</b>&nbsp;of {limit} questions left today
              </span>
            </div>
          )}
        </div>
      )}

      <div className="thread">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.content}
            {m.trace && <div className="trace">{m.trace}</div>}
            {m.role === "assistant" && m.cost != null && m.cost > 0 && (
              <div className="trace">This reading cost us ≈ {usd(m.cost)}</div>
            )}
            {m.role === "assistant" && m.scope && <ChartScopeNote scope={m.scope} />}
          </div>
        ))}
        {busy && <div className="bubble assistant">Reading your chart…</div>}
      </div>

      {quotaFull ? (
        <div className="card center quota-card">
          <div className="section-title">Your quota is full</div>
          <p className="dim" style={{ marginTop: 8 }}>
            {error || "You've used today's questions. Please come back tomorrow."}
          </p>
          {limit != null && <p className="note" style={{ marginTop: 6 }}>Resets at midnight (UTC).</p>}
        </div>
      ) : (
        <>
          {error && <p className="error">{error}</p>}
          <form className="composer card" onSubmit={ask}>
            <textarea
              placeholder="Ask your astrology question…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(e as unknown as React.FormEvent);
                }
              }}
              rows={2}
              required
            />
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <select value={methodology} onChange={(e) => setMethodology(e.target.value)} aria-label="Methodology">
                <option>Let the system decide</option>
                <option>Vedic</option>
                <option>KP</option>
                <option>Both</option>
              </select>
              <button className="btn btn-primary" disabled={busy}>
                {busy ? "…" : "Ask →"}
              </button>
            </div>
          </form>
          <p className="note" style={{ marginTop: 8 }}>
            Enter to send · Shift+Enter for a new line
          </p>
        </>
      )}

      <div style={{ marginTop: 26 }}>
        <CostPanel />
      </div>

      <p className="footnote">
        Every reading runs on an LLM that we pay for ourselves, so daily questions are limited — thanks for
        your cooperation.
      </p>
    </section>
  );
}
