import Link from "next/link";
import CornerControls from "@/app/components/CornerControls";
import { LoginForm } from "@/political-culture/components/LoginForm";
import { localePath, toLocale } from "@/app/i18n";
import { commonDictionary } from "@/app/dictionary";

export default async function Home({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const projectName = commonDictionary[lang].projects["political-culture"].name;

  return (
    <main className="auth" data-project="political-culture">
      <CornerControls />
      <div className="auth-panel">
        <div className="auth-intro">
          <div className="auth-brand">
            <span className="dot" aria-hidden="true" />
            {projectName}
          </div>
          <h1 className="auth-title">Entrar</h1>
          <p className="muted">Use o nome que foi cadastrado para você.</p>
        </div>
        <LoginForm />
        <Link href={localePath(lang, "/")} className="auth-back">
          Voltar para os projetos
        </Link>
      </div>
    </main>
  );
}
