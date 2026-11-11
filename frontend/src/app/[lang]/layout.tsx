import type { Metadata } from "next";
import { Schibsted_Grotesk } from "next/font/google";
import InlineScript from "@/app/components/InlineScript";
import { commonDictionary } from "@/app/dictionary";
import { LOCALES, type Locale, toLocale } from "@/app/i18n";

import "@/app/globals.css";

const sans = Schibsted_Grotesk({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  return { title: commonDictionary[toLocale((await params).lang)].title };
}

// Every page is prerendered in each language, and any other first segment
// gives a 404.
export function generateStaticParams(): { lang: Locale }[] {
  return LOCALES.map((lang) => ({ lang }));
}

export const dynamicParams = false;

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

export default async function RootLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}>): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);

  // The script sets data-theme before React hydrates, so React must not treat
  // the attribute as a mismatch.
  return (
    <html lang={lang} className={sans.variable} suppressHydrationWarning>
      <head>
        <InlineScript html={THEME_SCRIPT} />
      </head>
      <body>{children}</body>
    </html>
  );
}
