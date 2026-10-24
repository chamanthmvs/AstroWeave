"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { RunResponse } from "@/lib/types";

type Msg = { role: "user" | "assistant"; content: string; trace?: string };

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
  const ids = useRef<{ conversation_id?: string; session_id?: string }>({});

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
        },
      ]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "The reading could not be completed.");
    } finally {
      setBusy(false);
    }
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
        </div>
      )}

      <div className="thread">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.content}
            {m.trace && <div className="trace">{m.trace}</div>}
          </div>
        ))}
        {busy && <div className="bubble assistant">Reading your chart…</div>}
      </div>

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
    </section>
  );
}
