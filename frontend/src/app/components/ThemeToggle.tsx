"use client";

import { useLayoutEffect, useSyncExternalStore } from "react";
import { saveTheme } from "@/app/actions/theme";
import { logger } from "@/app/api/log/client-logger";

type Theme = "light" | "dark";

const DARK_QUERY = "(prefers-color-scheme: dark)";

// The theme lives in <html data-theme>: the root layout's script sets it from
// the "theme" cookie before the first paint, and without a saved choice the
// system preference applies.
function currentTheme(): Theme {
  const saved = document.documentElement.dataset.theme;
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

function subscribe(onChange: () => void): () => void {
  const system = window.matchMedia(DARK_QUERY);
  const observer = new MutationObserver(onChange);
  system.addEventListener("change", onChange);
  observer.observe(document.documentElement, {
    attributeFilter: ["data-theme"],
  });
  return () => {
    system.removeEventListener("change", onChange);
    observer.disconnect();
  };
}

// The server render has no DOM to read, so it renders the switch off. CSS
// places the knob from the real theme, so only aria-checked waits for
// hydration.
function serverTheme(): Theme {
  return "light";
}

export default function ThemeToggle(): React.ReactElement {
  const theme = useSyncExternalStore(subscribe, currentTheme, serverTheme);

  // When React renders <html> again in the browser (after a hydration mismatch,
  // such as a translator changing the page, or on a remount in development), it
  // drops the data-theme the root layout's script set. Put the saved theme back
  // before paint, but only when it is missing: right after a toggle, the cookie
  // may still hold the old choice. Same pattern as the script in layout.tsx.
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (root.dataset.theme) return;
    const saved = document.cookie.match(/(?:^|; )theme=(light|dark)(?:;|$)/);
    if (saved) root.dataset.theme = saved[1];
  }, []);

  function toggle(): void {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    saveTheme(next).catch((error: unknown) => {
      logger.error("Failed to save the theme", { theme: next, error });
    });
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={theme === "dark"}
      aria-label="Modo escuro"
      className="theme-toggle"
      onClick={toggle}
    >
      <span className="theme-toggle-knob" aria-hidden="true">
        <svg
          className="theme-toggle-sun"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
        >
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
        <svg
          className="theme-toggle-moon"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7z" />
        </svg>
      </span>
    </button>
  );
}
