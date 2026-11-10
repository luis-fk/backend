import { notFound } from "next/navigation";

// The site's languages. Every page's path starts with one of them, and
// <html lang> uses the same code.
export const LOCALES = ["pt-BR", "en"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "pt-BR";

// Each language's name, written in it: the label of the link to it.
export const LOCALE_NAMES: Record<Locale, string> = {
  "pt-BR": "Português",
  en: "English",
};

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

// The language in a route's [lang] segment; anything else is a 404.
export function toLocale(value: string): Locale {
  if (!isLocale(value)) notFound();
  return value;
}

export function otherLocale(lang: Locale): Locale {
  return lang === "pt-BR" ? "en" : "pt-BR";
}

// A path of the site in a language: localePath("en", "/plants/chat") is
// "/en/plants/chat", and localePath("en", "/") is "/en".
export function localePath(lang: Locale, path: string): string {
  return path === "/" ? `/${lang}` : `/${lang}${path}`;
}
