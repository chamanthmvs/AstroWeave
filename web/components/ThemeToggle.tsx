"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "light" ? "light" : "dark");
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("astroweave:theme", next);
    } catch {
      /* ignore */
    }
  }

  return (
    <button className="icon-btn" onClick={toggle} aria-label="Toggle light and dark" title="Toggle light / dark">
      {theme === "dark" ? "☾" : "☀"}
    </button>
  );
}
