"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import BirthFields, { emptyBirth, isGeocoded, type BirthForm } from "./BirthFields";
import ThemeToggle from "./ThemeToggle";

export default function AuthView() {
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [birth, setBirth] = useState<BirthForm>(emptyBirth);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "signin") {
        await signIn(email, password);
      } else {
        if (!isGeocoded(birth)) throw new Error("Please find your birth place first.");
        await register({
          email: email.trim().toLowerCase(),
          name: name.trim(),
          password,
          birth_details: {
            date: birth.date,
            time: birth.time.length === 5 ? `${birth.time}:00` : birth.time,
            latitude: birth.latitude as number,
            longitude: birth.longitude as number,
            utc_offset_hours: birth.utc_offset_hours as number,
            place_name: birth.place,
            date_known: true,
          },
        });
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-wrap">
      <div className="auth-card stack">
        <div className="auth-top">
          <ThemeToggle />
        </div>
        <div className="center">
          <div className="brand" style={{ justifyContent: "center" }}>
            <span className="brand-mark" aria-hidden />
            AstroWeave
          </div>
          <h1 className="section-title" style={{ marginTop: 14 }}>
            Your questions, read from every angle.
          </h1>
          <div className="usp">
            <span className="pill">
              <b>Easy to understand</b>
            </span>
            <span className="pill">
              <b>Factual</b>
            </span>
            <span className="pill">
              <b>Honest</b>
            </span>
          </div>
        </div>

        <div className="tabs" style={{ margin: "4px auto 8px" }}>
          <button className="tab" aria-selected={mode === "signin"} onClick={() => setMode("signin")}>
            Sign in
          </button>
          <button className="tab" aria-selected={mode === "register"} onClick={() => setMode("register")}>
            Register
          </button>
        </div>

        <form className="card card-glow" onSubmit={submit}>
          {mode === "register" && (
            <label className="field">
              <span>Your name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Maya Patel" required />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              required
            />
          </label>

          {mode === "register" && (
            <>
              <div className="eyebrow" style={{ margin: "6px 0 10px" }}>
                Birth details (fixed once, used for every reading)
              </div>
              <BirthFields value={birth} onChange={setBirth} />
            </>
          )}

          <button className="btn btn-primary btn-block" style={{ marginTop: 8 }} disabled={busy}>
            {busy ? "…" : mode === "signin" ? "Continue" : "Create account"}
          </button>
          <p className="error">{error}</p>
        </form>
      </div>
    </main>
  );
}
