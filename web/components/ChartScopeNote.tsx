"use client";

import { useState } from "react";
import type { ChartScope } from "@/lib/types";

// Transparency note shown only on the free "lite" tier: which charts were used
// in a reading and which heavier ones were skipped.
export default function ChartScopeNote({ scope }: { scope?: ChartScope | null }) {
  const [open, setOpen] = useState(false);
  if (!scope) return null;
  return (
    <div className="scope-note">
      <button type="button" className="btn-link" onClick={() => setOpen((o) => !o)}>
        ⓘ Which charts were used in this reading?
      </button>
      {open && (
        <div style={{ marginTop: 6 }} className="stack">
          <p className="note">{scope.note}</p>
          <p className="note"><b>Used:</b> {scope.included.join(", ")}.</p>
          <p className="note"><b>Not used (heavier, skipped on free hosting):</b> {scope.omitted.join(", ")}.</p>
        </div>
      )}
    </div>
  );
}
