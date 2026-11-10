"use client";

import Link from "next/link";
import CornerControls from "@/app/components/CornerControls";
import { commonDictionary } from "@/app/dictionary";
import { localePath } from "@/app/i18n";
import { useLocale } from "@/app/useLocale";

// A client component: not-found gets no params, so the language comes from the
// path.
export default function NotFound(): React.ReactElement {
  const lang = useLocale();
  const t = commonDictionary[lang];

  return (
    <main className="auth">
      <CornerControls />
      <div className="auth-panel">
        <div className="auth-intro">
          <h1 className="auth-title">{t.notFound.title}</h1>
          <p className="muted">{t.notFound.text}</p>
        </div>
        <Link href={localePath(lang, "/")} className="auth-back">
          {t.notFound.back}
        </Link>
      </div>
    </main>
  );
}
