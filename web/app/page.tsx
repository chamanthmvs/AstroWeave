"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import AuthView from "@/components/AuthView";
import AskTab from "@/components/AskTab";
import MatchTab from "@/components/MatchTab";
import ChartTab from "@/components/ChartTab";
import AtlasTab from "@/components/AtlasTab";
import ThemeToggle from "@/components/ThemeToggle";

type TabKey = "ask" | "match" | "chart" | "atlas";

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: "ask", label: "Ask", icon: "✦" },
  { key: "match", label: "Kundli Matching", icon: "☍" },
  { key: "chart", label: "My Chart", icon: "◐" },
  { key: "atlas", label: "Star Atlas", icon: "✧" },
];

export default function Home() {
  const { user, loading, signOut } = useAuth();
  const [tab, setTab] = useState<TabKey>("ask");

  if (loading) {
    return (
      <main className="auth-wrap">
        <p className="muted">Loading…</p>
      </main>
    );
  }

  if (!user) return <AuthView />;

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          AstroWeave
        </div>
        <div className="topbar-actions">
          <ThemeToggle />
          <button className="btn btn-ghost" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <main className="shell">
        <nav className="tabs" role="tablist" aria-label="Sections">
          {TABS.map((t) => (
            <button
              key={t.key}
              className="tab"
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
            >
              <span aria-hidden>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>

        {tab === "ask" && <AskTab />}
        {tab === "match" && <MatchTab />}
        {tab === "chart" && <ChartTab />}
        {tab === "atlas" && <AtlasTab />}
      </main>
    </>
  );
}
