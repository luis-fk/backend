import Link from "next/link";
import CornerControls from "@/app/components/CornerControls";
import { commonDictionary } from "@/app/dictionary";
import LoginForm from "@/cfflch/components/login-form";
import { cfflchDictionary } from "@/cfflch/dictionary";
import { localePath, toLocale } from "@/app/i18n";

export default async function Home({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const t = cfflchDictionary[lang].login;

  return (
    <main className="auth" data-project="cfflch">
      <CornerControls />
      <div className="auth-panel">
        <div className="auth-intro">
          <div className="auth-brand">
            <span className="dot" aria-hidden="true" />
            {commonDictionary[lang].projects.cfflch.name}
          </div>
          <h1 className="auth-title">{t.title}</h1>
          <p className="muted">{t.intro}</p>
        </div>
        <LoginForm />
        <Link href={localePath(lang, "/")} className="auth-back">
          {t.back}
        </Link>
      </div>
    </main>
  );
}
