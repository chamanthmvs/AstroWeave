"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import BirthFields, { emptyBirth, isGeocoded, type BirthForm } from "./BirthFields";
import ThemeToggle from "./ThemeToggle";

type Mode = "signin" | "register" | "request";

export default function AuthView() {
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [step, setStep] = useState<"email" | "details">("email"); // register only
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [birth, setBirth] = useState<BirthForm>(emptyBirth);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setStep("email");
    setError("");
    setDone("");
  }

  // Register step 1: only continue once we know this email is invited.
  async function checkAccess(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api<{ allowed: boolean; reason: string }>(
        `/auth/access-status?email=${encodeURIComponent(email.trim().toLowerCase())}`,
        { auth: false },
      );
      if (res.allowed) {
        setStep("details");
      } else if (res.reason === "domain") {
        setError("For now, only @gmail.com addresses are supported.");
      } else {
        setMode("request");
        setDone("");
        setError("That email isn't invited yet — you can request access below.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not check that email.");
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setDone("");
    setBusy(true);
    try {
      if (mode === "signin") {
        await signIn(email, password);
      } else if (mode === "request") {
        await api("/auth/request-access", {
          method: "POST",
          auth: false,
          body: { email: email.trim().toLowerCase(), name: name.trim() || undefined, note: note.trim() || undefined },
        });
        setDone("Thanks! Your request has been sent. You'll be able to sign up once the team approves it.");
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
      if (err instanceof ApiError && err.status === 403) {
        setMode("request");
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
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
          <p className="dim" style={{ marginTop: 8 }}>Specialist Vedic &amp; KP astrology — clear, factual, honest.</p>
        </div>

        <div className="tabs" style={{ margin: "4px auto 8px" }}>
          <button className="tab" aria-selected={mode === "signin"} onClick={() => switchMode("signin")}>Sign in</button>
          <button className="tab" aria-selected={mode === "register"} onClick={() => switchMode("register")}>Register</button>
          <button className="tab" aria-selected={mode === "request"} onClick={() => switchMode("request")}>Request access</button>
        </div>

        {done ? (
          <div className="card card-glow center stack">
            <div className="section-title">Request sent</div>
            <p className="dim">{done}</p>
            <button className="btn btn-ghost" onClick={() => switchMode("signin")}>Back to sign in</button>
          </div>
        ) : mode === "register" && step === "email" ? (
          // Step 1 — gate on access before showing the full form.
          <form className="card card-glow" onSubmit={checkAccess}>
            <label className="field">
              <span>Email</span>
              <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@gmail.com" required />
              <span className="note" style={{ marginTop: 4 }}>Gmail addresses only, for now. We&apos;ll check your invite first.</span>
            </label>
            <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Checking…" : "Continue"}</button>
            <p className="error">{error}</p>
            <p className="note center" style={{ marginTop: 10 }}>
              Don&apos;t have access yet?{" "}
              <button type="button" className="btn-link" onClick={() => switchMode("request")}>Request an invite</button>
            </p>
          </form>
        ) : (
          <form className="card card-glow" onSubmit={submit}>
            {(mode === "register" || mode === "request") && (
              <label className="field">
                <span>Your name{mode === "request" ? " (optional)" : ""}</span>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Maya Patel" required={mode === "register"} />
              </label>
            )}

            <label className="field">
              <span>Email</span>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@gmail.com"
                required
                readOnly={mode === "register"}
              />
              {mode === "request" && <span className="note" style={{ marginTop: 4 }}>Gmail addresses only, for now.</span>}
            </label>

            {mode === "signin" && (
              <label className="field">
                <span>Password</span>
                <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Your password" required />
              </label>
            )}

            {mode === "register" && (
              <>
                <label className="field">
                  <span>Password</span>
                  <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" required />
                </label>
                <div className="eyebrow" style={{ margin: "6px 0 10px" }}>Birth details (fixed once, used for every reading)</div>
                <BirthFields value={birth} onChange={setBirth} />
              </>
            )}

            {mode === "request" && (
              <label className="field">
                <span>A note to the team (optional)</span>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Anything that helps us know you" rows={2} />
              </label>
            )}

            <button className="btn btn-primary btn-block" style={{ marginTop: 8 }} disabled={busy}>
              {busy ? "…" : mode === "signin" ? "Continue" : mode === "request" ? "Request access" : "Create account"}
            </button>
            <p className="error">{error}</p>
          </form>
        )}
      </div>
    </main>
  );
}
