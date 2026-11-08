import Link from "next/link";
import ThemeToggle from "@/app/components/ThemeToggle";

export default function NotFound(): React.ReactElement {
  return (
    <main className="auth">
      <ThemeToggle />
      <div className="auth-panel">
        <div className="auth-intro">
          <h1 className="auth-title">Página não encontrada</h1>
          <p className="muted">Este endereço não existe ou mudou.</p>
        </div>
        <Link href="/" className="auth-back">
          Voltar para os projetos
        </Link>
      </div>
    </main>
  );
}
