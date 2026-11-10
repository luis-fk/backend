import Link from "next/link";
import CornerControls from "@/app/components/CornerControls";
import { LoginForm } from "@/plants/components/LoginForm";
import { plantsDictionary } from "@/plants/dictionary";
import { commonDictionary } from "@/app/dictionary";
import { localePath, toLocale } from "@/app/i18n";

export default async function Home({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const projectName = commonDictionary[lang].projects.plants.name;
  const t = plantsDictionary[lang];

  return (
    <main className="auth" data-project="plants">
      <CornerControls />
      <div className="auth-panel">
        <div className="auth-intro">
          <div className="auth-brand">
            <span className="dot" aria-hidden="true" />
            {projectName}
          </div>
          <h1 className="auth-title">{t.login.title}</h1>
          <p className="muted">{t.login.intro}</p>
        </div>
        <LoginForm />
        <Link href={localePath(lang, "/")} className="auth-back">
          {t.login.back}
        </Link>
      </div>
    </main>
  );
}
