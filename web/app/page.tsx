"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import AuthView from "@/components/AuthView";
import AskTab from "@/components/AskTab";
import MatchTab from "@/components/MatchTab";
import ChartTab from "@/components/ChartTab";
import AtlasTab from "@/components/AtlasTab";
import AdminTab from "@/components/AdminTab";
import ThemeToggle from "@/components/ThemeToggle";
import QuotaBadge from "@/components/QuotaBadge";

type TabKey = "chart" | "ask" | "match" | "atlas" | "admin";

const TABS: { key: TabKey; label: string; icon: string; adminOnly?: boolean }[] = [
  { key: "chart", label: "My Chart", icon: "◐" },
  { key: "ask", label: "Ask", icon: "✦" },
  { key: "match", label: "Kundli Matching", icon: "☍" },
  { key: "atlas", label: "Celestial Atlas", icon: "✧" },
  { key: "admin", label: "Admin", icon: "⚙", adminOnly: true },
];

export default function Home() {
  const { user, loading, signOut } = useAuth();
  const [tab, setTab] = useState<TabKey>("chart");

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
        <div className="topbar-left">
          <div className="brand">
            <span className="brand-mark" aria-hidden />
            AstroWeave
          </div>
          <QuotaBadge />
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
          {TABS.filter((t) => !t.adminOnly || user.is_admin).map((t) => (
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
        {tab === "admin" && user.is_admin && <AdminTab />}
      </main>
    </>
  );
}
