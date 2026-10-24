"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export type BirthForm = {
  date: string;
  time: string;
  place: string;
  latitude: number | null;
  longitude: number | null;
  utc_offset_hours: number | null;
};

export const emptyBirth: BirthForm = {
  date: "",
  time: "",
  place: "",
  latitude: null,
  longitude: null,
  utc_offset_hours: null,
};

export function isGeocoded(b: BirthForm): boolean {
  return b.latitude !== null && b.longitude !== null && b.utc_offset_hours !== null;
}

export default function BirthFields({
  value,
  onChange,
}: {
  value: BirthForm;
  onChange: (next: BirthForm) => void;
}) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  async function geocode() {
    if (!value.place.trim()) return;
    setBusy(true);
    setStatus("");
    try {
      const loc = await api<{ latitude: number; longitude: number; utc_offset_hours: number; place_name?: string }>(
        `/geocode?place=${encodeURIComponent(value.place.trim())}`,
        { auth: false },
      );
      onChange({
        ...value,
        latitude: loc.latitude,
        longitude: loc.longitude,
        utc_offset_hours: loc.utc_offset_hours,
        place: loc.place_name || value.place,
      });
      setStatus(`Found: ${loc.latitude.toFixed(2)}, ${loc.longitude.toFixed(2)} (UTC+${loc.utc_offset_hours})`);
    } catch (e: unknown) {
      setStatus(e instanceof Error ? e.message : "Could not find that place.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="row-2">
        <label className="field">
          <span>Birth date</span>
          <input
            type="date"
            min="1900-01-01"
            value={value.date}
            onChange={(e) => onChange({ ...value, date: e.target.value })}
            required
          />
        </label>
        <label className="field">
          <span>Birth time</span>
          <input
            type="time"
            step={1}
            value={value.time}
            onChange={(e) => onChange({ ...value, time: e.target.value })}
            required
          />
        </label>
      </div>
      <div className="geo-row">
        <label className="field">
          <span>Birth place (India)</span>
          <input
            placeholder="e.g. Chennai, India"
            value={value.place}
            onChange={(e) => onChange({ ...value, place: e.target.value, latitude: null, longitude: null, utc_offset_hours: null })}
          />
        </label>
        <button type="button" className="btn btn-ghost" onClick={geocode} disabled={busy || !value.place.trim()}>
          {busy ? "…" : "Find"}
        </button>
      </div>
      <p className={isGeocoded(value) ? "ok" : "note"}>{status || "Enter a place and press Find to locate it."}</p>
    </>
  );
}
