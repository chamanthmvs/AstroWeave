"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Conversation } from "@/lib/types";

function when(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function ConversationHistory({
  onOpen,
  onClose,
  activeId,
}: {
  onOpen: (id: string) => void;
  onClose: () => void;
  activeId?: string;
}) {
  const [items, setItems] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api<{ conversations: Conversation[] }>("/conversations");
      setItems(res.conversations);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load your history.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function remove(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this conversation? This can't be undone.")) return;
    setBusyId(id);
    try {
      await api(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
      setItems((xs) => xs.filter((x) => x.conversation_id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not delete that conversation.");
    } finally {
      setBusyId("");
    }
  }

  return (
    <div className="card">
      <div className="toolbar" style={{ marginBottom: 10 }}>
        <div className="section-title" style={{ marginRight: "auto" }}>Your past readings</div>
        <button className="btn-link" onClick={load} disabled={loading}>Refresh</button>
        <button className="btn-link" onClick={onClose}>Back to Ask</button>
      </div>

      {loading && <p className="muted">Loading your conversations…</p>}
      {error && !loading && <p className="error">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="note">No past readings yet. Your questions and answers will appear here once you ask.</p>
      )}

      {items.length > 0 && (
        <div className="hist-list">
          {items.map((c) => (
            <div
              key={c.conversation_id}
              className={`hist-row${c.conversation_id === activeId ? " hist-active" : ""}`}
              onClick={() => onOpen(c.conversation_id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter") onOpen(c.conversation_id); }}
            >
              <div className="hist-main">
                <div className="hist-title">{c.title?.trim() || "Untitled reading"}</div>
                <div className="note">{when(c.updated_at)}</div>
              </div>
              <button
                className="btn-link hist-del"
                onClick={(e) => remove(c.conversation_id, e)}
                disabled={busyId === c.conversation_id}
                aria-label="Delete conversation"
              >
                {busyId === c.conversation_id ? "…" : "Delete"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
