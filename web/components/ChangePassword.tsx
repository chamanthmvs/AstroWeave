"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function ChangePassword() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    if (next.length < 8) {
      setErr("New password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await api("/auth/change-password", { method: "POST", body: { current_password: current, new_password: next } });
      setMsg("Password changed.");
      setCurrent("");
      setNext("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account">
      <button className="icon-btn" onClick={() => setOpen((o) => !o)} aria-label="Change password" title="Change password">
        🔑
      </button>
      {open && (
        <div className="popover card">
          <div className="section-title" style={{ fontSize: "1.1rem" }}>Change password</div>
          <form onSubmit={submit} style={{ marginTop: 10 }}>
            <label className="field">
              <span>Current password</span>
              <input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
            </label>
            <label className="field">
              <span>New password</span>
              <input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} placeholder="At least 8 characters" required />
            </label>
            <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "…" : "Update password"}</button>
            {msg && <p className="ok">{msg}</p>}
            {err && <p className="error">{err}</p>}
          </form>
        </div>
      )}
    </div>
  );
}
