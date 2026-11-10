"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LOCALE_NAMES, localePath, otherLocale } from "@/app/i18n";
import { useLocale } from "@/app/useLocale";

// The same page in the other language, named in that language. The header on
// phones shows the language's code instead (globals.css): the name stays for
// screen readers, and the code is part of the link's name too, so voice control
// can follow what is on screen.
export default function LanguageLink(): React.ReactElement {
  const lang = useLocale();
  const other = otherLocale(lang);
  // The path without its language segment: "/pt-BR/plants" is "/plants".
  const path = usePathname().slice(lang.length + 1) || "/";

  return (
    <Link
      href={localePath(other, path)}
      // A prefetch goes through the proxy, which would save the other language
      // in the lang cookie without a click.
      prefetch={false}
      hrefLang={other}
      lang={other}
      className="language-link"
    >
      <span className="language-name">{LOCALE_NAMES[other]}</span>{" "}
      <span className="language-code">{other.slice(0, 2).toUpperCase()}</span>
    </Link>
  );
}
