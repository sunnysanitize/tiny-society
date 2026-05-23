"use client";
import { useEffect, useState } from "react";

export type Breakpoint = "phone" | "tablet" | "desktop";

const PHONE_MAX = 640;   // <= phone
const TABLET_MAX = 1024; // <= tablet, otherwise desktop

function classify(width: number): Breakpoint {
  if (width <= PHONE_MAX) return "phone";
  if (width <= TABLET_MAX) return "tablet";
  return "desktop";
}

/**
 * SSR-safe viewport hook. Defaults to "desktop" on the server / first render,
 * then corrects on mount and tracks resize.
 */
export function useViewport() {
  // Default to desktop so SSR markup matches the most common case and never
  // references `window` during render.
  const [width, setWidth] = useState<number>(1440);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    function update() {
      setWidth(window.innerWidth);
    }
    update();
    setMounted(true);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const breakpoint = classify(width);
  return {
    width,
    breakpoint,
    isPhone: breakpoint === "phone",
    isTablet: breakpoint === "tablet",
    isDesktop: breakpoint === "desktop",
    /** narrow = phone or tablet (where side-by-side layouts should stack) */
    isNarrow: breakpoint !== "desktop",
    /** true once corrected on the client; useful to avoid layout flash */
    mounted,
  };
}
