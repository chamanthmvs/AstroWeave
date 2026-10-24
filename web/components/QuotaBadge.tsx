"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Quota = { used: number; limit: number | null; remaining: number | null };

// Small live counter of questions left today, shown top-left in the bar.
// Refreshes on mount and whenever the Ask tab fires "astroweave:quota-refresh".
export default function QuotaBadge() {
  const [quota, setQuota] = useState<Quota | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await api<{ user: Quota }>("/usage");
        if (active) setQuota(data.user);
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

  if (!quota || quota.limit == null) return null;
  const left = quota.remaining ?? quota.limit;
  return (
    <div className="quota-badge" title="Questions remaining today">
      <span className={`quota-dot ${left <= 0 ? "empty" : ""}`} aria-hidden />
      {left}/{quota.limit} left today
    </div>
  );
}
