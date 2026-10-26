"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { RunResponse } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import CostPanel, { usd } from "./CostPanel";

type Msg = { role: "user" | "assistant"; content: string; trace?: string; cost?: number; startsTopic?: boolean };
type Quota = { used: number; limit: number | null; remaining: number | null };

const STORE_KEY = "astroweave:ask-thread";

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function AskTab() {
  const { readingsEnabled, readingsMessage } = useAuth();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [query, setQuery] = useState("");
  const [methodology, setMethodology] = useState("Let the system decide");
  const [mode, setMode] = useState<"followup" | "new">("new");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [quotaFull, setQuotaFull] = useState(false);
  const [quota, setQuota] = useState<Quota | null>(null);
  const ids = useRef<{ conversation_id?: string; session_id?: string }>({});

  // Keep the current thread across page refreshes (per browser) so you don't lose
  // your questions and answers. Server-side history exists too; this is the quick,
  // local convenience layer.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as { messages?: Msg[]; ids?: { conversation_id?: string; session_id?: string } };
        if (saved.messages?.length) {
          setMessages(saved.messages);
          ids.current = saved.ids || {};
          setMode("followup");
        }
      }
    } catch {
      /* storage unavailable (private mode, etc.) — thread just won't persist */
    }
  }, []);

  useEffect(() => {
    try {
      if (messages.length) localStorage.setItem(STORE_KEY, JSON.stringify({ messages, ids: ids.current }));
      else localStorage.removeItem(STORE_KEY);
    } catch {
      /* ignore */
    }
  }, [messages]);

  function clearThread() {
    setMessages([]);
    ids.current = {};
    setMode("new");
    setError("");
    try {
      localStorage.removeItem(STORE_KEY);
    } catch {
      /* ignore */
    }
  }

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
    // "New question" starts a fresh conversation (standalone, no prior context);
    // "Follow-up" continues the current one so the model sees earlier Q&A.
    const startingNew = mode === "new" || messages.length === 0;
    if (startingNew) ids.current = {};
    setMessages((m) => [...m, { role: "user", content: text, startsTopic: startingNew && m.length > 0 }]);
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
          conversation_id: startingNew ? undefined : ids.current.conversation_id,
          session_id: startingNew ? undefined : ids.current.session_id,
        },
      });
      ids.current = { conversation_id: res.conversation_id, session_id: res.session_id };
      if (mode === "new") setMode("followup"); // after a new topic, keep going as follow-ups
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

  if (!readingsEnabled) {
    return (
      <section>
        <div className="hero">
          <div className="eyebrow">Personal reading</div>
          <h1>Readings are paused</h1>
        </div>
        <div className="card center" style={{ maxWidth: 620, margin: "0 auto" }}>
          <p className="dim">
            {readingsMessage ||
              "AstroWeave is running on a free tier right now, so live readings are paused. We'll switch them back on soon."}
          </p>
          <p className="note" style={{ marginTop: 10 }}>
            In the meantime, your <b>My Chart</b>, <b>Numerology</b>, <b>Celestial Atlas</b> and Kundli points are
            all available.
          </p>
        </div>
      </section>
    );
  }

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
          <div key={i}>
            {m.startsTopic && (
              <div className="topic-divider"><span>New question</span></div>
            )}
            <div className={`bubble ${m.role}`}>
              {m.content}
              {m.trace && <div className="trace">{m.trace}</div>}
              {m.role === "assistant" && m.cost != null && m.cost > 0 && (
                <div className="trace">This reading cost us ≈ {usd(m.cost)}</div>
              )}
            </div>
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
          {messages.length > 0 && (
            <div className="ask-controls">
              <div className="seg" role="group" aria-label="Question mode">
                <button
                  type="button"
                  className={mode === "followup" ? "seg-on" : ""}
                  onClick={() => setMode("followup")}
                >
                  Follow-up
                </button>
                <button
                  type="button"
                  className={mode === "new" ? "seg-on" : ""}
                  onClick={() => setMode("new")}
                >
                  New question
                </button>
              </div>
              <span className="note">
                {mode === "followup"
                  ? "Continues this thread — the reading sees your earlier questions."
                  : "Starts fresh — answered on its own, without the thread above."}
              </span>
              <button type="button" className="btn-link" onClick={clearThread} style={{ marginLeft: "auto" }}>
                Clear thread
              </button>
            </div>
          )}
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
