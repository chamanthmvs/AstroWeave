"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Summary = {
  overall: { users: number; runs: number; tokens: number; cost_usd: number };
  by_user: { owner: string; runs: number; input_tokens: number; output_tokens: number; cache_read_tokens: number; cost_usd: number }[];
  by_model: { model: string; runs: number; tokens: number; cost_usd: number }[];
};
type Allowed = { email: string; invited_by: string | null; created_at: string };
type AccessReq = { email: string; name: string | null; note: string | null; created_at: string };

const money = (n: number) => `$${(n ?? 0).toFixed(4)}`;
const num = (n: number) => (n ?? 0).toLocaleString();

export default function AdminTab() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [allowed, setAllowed] = useState<Allowed[]>([]);
  const [requests, setRequests] = useState<AccessReq[]>([]);
  const [newEmail, setNewEmail] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [s, a, r] = await Promise.all([
        api<Summary>("/admin/summary"),
        api<{ allowed: Allowed[] }>("/admin/allowlist"),
        api<{ requests: AccessReq[] }>("/admin/access-requests"),
      ]);
      setSummary(s);
      setAllowed(a.allowed);
      setRequests(r.requests);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load admin data.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function grant(email: string) {
    await api("/admin/allowlist", { method: "POST", body: { email } });
    setNewEmail("");
    load();
  }
  async function revoke(email: string) {
    await api(`/admin/allowlist/${encodeURIComponent(email)}`, { method: "DELETE" });
    load();
  }
  async function approve(email: string) {
    await api(`/admin/access-requests/${encodeURIComponent(email)}/approve`, { method: "POST" });
    load();
  }
  async function decline(email: string) {
    await api(`/admin/access-requests/${encodeURIComponent(email)}`, { method: "DELETE" });
    load();
  }

  return (
    <section className="stack">
      <div className="hero">
        <div className="eyebrow">Admin</div>
        <h1>Dashboard</h1>
        <p>Usage and cost across all users, and who may join. Question text is never stored or shown.</p>
      </div>

      {error && <p className="error">{error}</p>}

      {summary && (
        <div className="facts">
          <div className="fact"><div className="k">Users</div><div className="v">{num(summary.overall.users)}</div></div>
          <div className="fact"><div className="k">Questions</div><div className="v">{num(summary.overall.runs)}</div></div>
          <div className="fact"><div className="k">Tokens</div><div className="v">{num(summary.overall.tokens)}</div></div>
          <div className="fact"><div className="k">Cost</div><div className="v">{money(summary.overall.cost_usd)}</div></div>
        </div>
      )}

      {summary && summary.by_user.length > 0 && (
        <div className="card">
          <div className="section-title">By user</div>
          <div className="admin-table" role="table">
            <div className="admin-row admin-head">
              <span>Email</span><span>Questions</span><span>Tokens</span><span>Cost</span>
            </div>
            {summary.by_user.map((u) => (
              <div className="admin-row" key={u.owner}>
                <span className="mono">{u.owner}</span>
                <span>{num(u.runs)}</span>
                <span>{num(u.input_tokens + u.output_tokens + u.cache_read_tokens)}</span>
                <span>{money(u.cost_usd)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary && summary.by_model.length > 0 && (
        <div className="card">
          <div className="section-title">By model</div>
          <div className="admin-table">
            <div className="admin-row admin-head"><span>Model</span><span>Questions</span><span>Tokens</span><span>Cost</span></div>
            {summary.by_model.map((m) => (
              <div className="admin-row" key={m.model}>
                <span className="mono">{m.model}</span><span>{num(m.runs)}</span><span>{num(m.tokens)}</span><span>{money(m.cost_usd)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="section-title">Access requests {requests.length > 0 && <span className="pill">{requests.length}</span>}</div>
        {requests.length === 0 ? (
          <p className="note" style={{ marginTop: 8 }}>No pending requests.</p>
        ) : (
          <div className="admin-table" style={{ marginTop: 10 }}>
            {requests.map((r) => (
              <div className="admin-row admin-row-wide" key={r.email}>
                <span className="mono">{r.email}</span>
                <span className="dim">{r.name || "—"}{r.note ? ` · ${r.note}` : ""}</span>
                <span className="admin-actions">
                  <button className="btn btn-primary" onClick={() => approve(r.email)}>Approve</button>
                  <button className="btn btn-ghost" onClick={() => decline(r.email)}>Decline</button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="section-title">Allowlist</div>
        <div className="geo-row" style={{ marginTop: 10 }}>
          <label className="field">
            <span>Invite an email</span>
            <input value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="person@gmail.com" />
          </label>
          <button className="btn btn-primary" disabled={!newEmail.trim()} onClick={() => grant(newEmail.trim().toLowerCase())}>
            Add
          </button>
        </div>
        {allowed.length > 0 && (
          <div className="admin-table" style={{ marginTop: 12 }}>
            {allowed.map((a) => (
              <div className="admin-row admin-row-wide" key={a.email}>
                <span className="mono">{a.email}</span>
                <span className="dim">invited by {a.invited_by || "—"}</span>
                <span className="admin-actions">
                  <button className="btn btn-ghost" onClick={() => revoke(a.email)}>Remove</button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
