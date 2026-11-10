import Link from "next/link";
import CornerControls from "@/app/components/CornerControls";
import { LoginForm } from "@/political-culture/components/LoginForm";
import { localePath, toLocale } from "@/app/i18n";
import { commonDictionary } from "@/app/dictionary";
import { politicalCultureDictionary } from "@/political-culture/dictionary";

export default async function Home({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const projectName = commonDictionary[lang].projects["political-culture"].name;
  const t = politicalCultureDictionary[lang].login;

  return (
    <main className="auth" data-project="political-culture">
      <CornerControls />
      <div className="auth-panel">
        <div className="auth-intro">
          <div className="auth-brand">
            <span className="dot" aria-hidden="true" />
            {projectName}
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
