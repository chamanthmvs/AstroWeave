"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CostSummary, CostWindow } from "@/lib/types";

export function usd(n: number): string {
  if (!n || n <= 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

// Transparency panel in the Ask tab: what this user's readings have cost us.
// Refreshes on mount and whenever a reading completes (astroweave:quota-refresh).
export default function CostPanel() {
  const [cost, setCost] = useState<CostSummary | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await api<CostSummary>("/usage/cost");
        if (active) setCost(data);
      } catch {
        /* non-fatal */
      }
    };
    load();
    const handler = () => load();
    window.addEventListener("astroweave:quota-refresh", handler);
    return () => {
      active = false;
      window.removeEventListener("astroweave:quota-refresh", handler);
    };
  }, []);

  if (!cost) return null;

  const stat = (label: string, w: CostWindow) => (
    <div className="cost-stat">
      <div className="k">{label}</div>
      <div className="v">{usd(w.cost_usd)}</div>
      <div className="note">{w.runs} {w.runs === 1 ? "reading" : "readings"}</div>
    </div>
  );

  return (
    <div className="card cost-panel">
      <div className="section-title" style={{ fontSize: "1.15rem" }}>What your readings cost us</div>
      <p className="note" style={{ marginTop: 4 }}>
        We cover the LLM bill ourselves — thank you for using AstroWeave thoughtfully. Figures are estimated.
      </p>
      <div className="cost-row" style={{ marginTop: 14 }}>
        {stat("Today", cost.today)}
        {stat("Yesterday", cost.yesterday)}
        {stat("All time", cost.total)}
      </div>
      <button className="btn-link" style={{ marginTop: 10 }} onClick={() => setOpen((o) => !o)}>
        {open ? "Hide full statistics" : "Full statistics →"}
      </button>
      {open && (
        <div className="cost-row" style={{ marginTop: 12 }}>
          {stat("Last 3 days", cost.last_3_days)}
          {stat("Last 7 days", cost.last_7_days)}
          {stat("Last 14 days", cost.last_14_days)}
          {stat("Last 30 days", cost.last_30_days)}
        </div>
      )}
    </div>
  );
}
