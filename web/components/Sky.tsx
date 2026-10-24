"use client";

import { useEffect, useRef } from "react";

// The animated cosmos behind everything: nebula, a faint moon, a subtle
// constellation, layered stars, and an occasional shooting star. Pointer
// movement drives a depth parallax (nearer layers move more); disabled when
// the viewer prefers reduced motion.
export default function Sky() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let raf = 0;
    const onMove = (e: PointerEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const x = e.clientX / window.innerWidth - 0.5;
        const y = e.clientY / window.innerHeight - 0.5;
        el.style.setProperty("--px", x.toFixed(3));
        el.style.setProperty("--py", y.toFixed(3));
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="starfield" aria-hidden ref={ref}>
      <div className="nebula" />
      <div className="moon" />
      <svg className="constellation" viewBox="0 0 280 200" fill="none">
        <polyline
          points="20,44 72,20 112,70 164,50 152,122 92,142 112,70 164,50 206,112"
          stroke="currentColor"
          strokeWidth="1"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {[
          [20, 44],
          [72, 20],
          [112, 70],
          [164, 50],
          [152, 122],
          [92, 142],
          [206, 112],
        ].map(([cx, cy], i) => (
          <circle key={i} cx={cx} cy={cy} r={i % 3 === 0 ? 2.2 : 1.6} fill="#fff" />
        ))}
      </svg>
      <div className="stars stars-sm" />
      <div className="stars stars-md" />
      <div className="stars stars-lg" />
      <div className="shooting" />
    </div>
  );
}
