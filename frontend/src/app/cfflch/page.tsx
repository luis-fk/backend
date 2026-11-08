import Link from "next/link";
import LoginForm from "@/cfflch/components/login-form";

export default function Home(): React.ReactElement {
  return (
    <main className="auth" data-project="cfflch">
      <div className="auth-panel">
        <div className="auth-intro">
          <div className="auth-brand">
            <span className="dot" aria-hidden="true" />
            CFFLCH
          </div>
          <h1 className="auth-title">Entrar</h1>
          <p className="muted">Use o nome que foi cadastrado para você.</p>
        </div>
        <LoginForm />
        <Link href="/" className="auth-back">
          Voltar para os projetos
        </Link>
      </div>
    </main>
  );
}
