import Link from "next/link";
import ThemeToggle from "@/app/components/ThemeToggle";
import { LoginForm } from "@/app/political-culture/components/LoginForm";
import { PROJECTS } from "@/app/projects";

const projectName = PROJECTS.find(
  (project) => project.key === "political-culture",
)?.name;

export default function Home(): React.ReactElement {
  return (
    <main className="auth" data-project="political-culture">
      <ThemeToggle />
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
        <Link href="/" className="auth-back">
          Voltar para os projetos
        </Link>
      </div>
    </main>
  );
}
