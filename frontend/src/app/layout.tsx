import type { Metadata } from "next";
import { Schibsted_Grotesk } from "next/font/google";

import "@/app/globals.css";

const sans = Schibsted_Grotesk({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Projetos",
};

// Applies the theme saved by ThemeToggle (the "theme" cookie) before the first
// paint, so nothing flashes on load, and again when the browser restores the
// page from its back/forward cache, which keeps the theme the page had when the
// visitor left it. Without a saved choice, the CSS follows the system.
// Reading the cookie on the server instead would render every page on each
// request; read here, it leaves the pages static.
const THEME_SCRIPT = `(function () {
  function apply() {
    try {
      var saved = document.cookie.match(/(?:^|; )theme=(light|dark)(?:;|$)/);
      if (saved) document.documentElement.dataset.theme = saved[1];
    } catch (error) {}
  }
  apply();
  addEventListener("pageshow", function (event) {
    if (event.persisted) apply();
  });
})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  // The script sets data-theme before React hydrates, so React must not treat
  // the attribute as a mismatch.
  return (
    <html lang="pt-BR" className={sans.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
