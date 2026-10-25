"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import AuthView from "@/components/AuthView";
import AskTab from "@/components/AskTab";
import MatchTab from "@/components/MatchTab";
import ChartTab from "@/components/ChartTab";
import AtlasTab from "@/components/AtlasTab";
import NumerologyTab from "@/components/NumerologyTab";
import AdminTab from "@/components/AdminTab";
import ThemeToggle from "@/components/ThemeToggle";
import QuotaBadge from "@/components/QuotaBadge";
import ChangePassword from "@/components/ChangePassword";

type TabKey = "chart" | "ask" | "match" | "numerology" | "atlas" | "admin";

// Tabs that need the (sleepy) chart service. Disabled until it's awake.
const CHART_TABS: TabKey[] = ["chart", "ask"];

const TABS: { key: TabKey; label: string; icon: string; adminOnly?: boolean }[] = [
  { key: "chart", label: "My Chart", icon: "◐" },
  { key: "ask", label: "Ask", icon: "✦" },
  { key: "match", label: "Kundli Matching", icon: "☍" },
  { key: "numerology", label: "Numerology", icon: "№" },
  { key: "atlas", label: "Celestial Atlas", icon: "✧" },
  { key: "admin", label: "Admin", icon: "⚙", adminOnly: true },
];

export default function Home() {
  const { user, loading, signOut } = useAuth();
  const [tab, setTab] = useState<TabKey>("chart");
  const [chartReady, setChartReady] = useState<boolean | null>(null); // null = unknown
  const redirected = useRef(false);

  // Poll readiness while signed in; polling also helps wake a sleeping service.
  useEffect(() => {
    if (!user) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const r = await api<{ chart_service: boolean }>("/ready", { auth: false });
        if (stop) return;
        setChartReady(r.chart_service);
        if (!r.chart_service) {
          // On first detection, move off a chart-only tab so the user isn't stuck.
          if (!redirected.current) {
            redirected.current = true;
            setTab((t) => (CHART_TABS.includes(t) ? "numerology" : t));
          }
          timer = setTimeout(poll, 10000);
        }
      } catch {
        if (!stop) timer = setTimeout(poll, 10000);
      }
    };
    poll();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [user]);

  if (loading) {
    return (
      <main className="auth-wrap">
        <p className="muted">Loading…</p>
      </main>
    );
  }

  if (!user) return <AuthView />;

  const waking = chartReady === false;

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
          <ChangePassword />
          <ThemeToggle />
          <button className="btn btn-ghost" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <main className="shell">
        <nav className="tabs" role="tablist" aria-label="Sections">
          {TABS.filter((t) => !t.adminOnly || user.is_admin).map((t) => {
            const disabled = waking && CHART_TABS.includes(t.key);
            return (
              <button
                key={t.key}
                className="tab"
                role="tab"
                aria-selected={tab === t.key}
                disabled={disabled}
                title={disabled ? "Waking the astrology engine…" : undefined}
                onClick={() => !disabled && setTab(t.key)}
              >
                <span aria-hidden>{t.icon}</span>
                {t.label}
                {disabled && <span aria-hidden> ·</span>}
              </button>
            );
          })}
        </nav>

        {waking && (
          <div className="banner">
            ✦ The astrology engine is waking up (free hosting sleeps when idle). <b>My Chart</b> and <b>Ask</b>{" "}
            will enable in a moment — meanwhile try <b>Numerology</b> or the <b>Celestial Atlas</b>.
          </div>
        )}

        {tab === "ask" && (waking ? null : <AskTab />)}
        {tab === "match" && <MatchTab />}
        {tab === "chart" && (waking ? null : <ChartTab />)}
        {tab === "numerology" && <NumerologyTab />}
        {tab === "atlas" && <AtlasTab />}
        {tab === "admin" && user.is_admin && <AdminTab />}
      </main>
    </>
  );
}
