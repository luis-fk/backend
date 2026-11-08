"use client";

import { useState, useCallback } from "react";
import { useSession } from "@/app/actions/useSession";
import {
  useAdmissionSearch,
  AdmissionResult,
} from "@/cfflch/hooks/use-admission-search";
import Toast from "@/app/components/Toast";
import "@/cfflch/css/search.css";

function listStatus(count: number): string {
  if (count === 0) return "Não aparece em nenhuma lista";
  if (count === 1) return "Aparece em 1 lista";
  return `Aparece em ${count} listas`;
}

function ResultItem({
  result,
}: {
  result: AdmissionResult;
}): React.ReactElement {
  return (
    <li className="search-result">
      <span className="search-result-name">{result.student_name}</span>
      <span className="search-result-status muted">
        {listStatus(result.pdf_entries.length)}
      </span>
      {result.pdf_entries.map((pdf) => (
        <a
          key={pdf.url}
          className="search-result-link"
          href={pdf.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {pdf.search_title}
        </a>
      ))}
    </li>
  );
}

export default function SearchForm(): React.ReactElement {
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;
  const session = useSession("cfflch");
  const { results, loading, error, search, clearError } = useAdmissionSearch(
    serverUrl,
    session?.token,
  );

  const [namesValue, setNamesValue] = useState("");
  const [currentYear] = useState(() => new Date().getFullYear());
  const years = Array.from(
    { length: currentYear - 2000 + 1 },
    (_, i) => currentYear - i,
  );
  const [year, setYear] = useState(currentYear);
  const [className, setClassName] = useState("");
  const [searchedNames, setSearchedNames] = useState<string[]>([]);

  // While the search runs, each name without an answer yet gets a pending row.
  const pendingNames = loading
    ? searchedNames.filter(
        (name) =>
          !results.some(
            (r) => r.student_name.trim().toLowerCase() === name.toLowerCase(),
          ),
      )
    : [];

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault();
      const names = namesValue
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      if (names.length === 0) return;

      setSearchedNames(names);
      await search({
        names,
        year,
        ...(className.trim() ? { class_name: className.trim() } : {}),
      });
    },
    [namesValue, year, className, search],
  );

  return (
    <main className="page page-narrow">
      <div className="page-header">
        <h1 className="page-title">Buscar alunos</h1>
        <p className="muted">
          Procuramos cada nome nas listas de aprovados publicadas em PDF.
        </p>
      </div>

      <form className="search-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="names" className="field-label">
            Nomes, um por linha
          </label>
          <textarea
            id="names"
            className="textarea"
            rows={5}
            value={namesValue}
            onChange={(e) => setNamesValue(e.target.value)}
            placeholder={"João Silva\nMaria Souza"}
            disabled={loading}
          />
        </div>

        <div className="search-options">
          <div className="field search-year">
            <label htmlFor="year" className="field-label">
              Ano
            </label>
            <select
              id="year"
              className="select"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              disabled={loading}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
          <div className="field search-class">
            <label htmlFor="class-name" className="field-label">
              Turma (opcional)
            </label>
            <input
              id="class-name"
              type="text"
              className="input"
              value={className}
              onChange={(e) => setClassName(e.target.value)}
              placeholder="Turma A"
              disabled={loading}
            />
          </div>
        </div>

        <button type="submit" className="button" disabled={loading || !session}>
          {loading ? "Buscando…" : "Buscar"}
        </button>
      </form>

      {session === null && (
        <p className="muted">
          Não foi possível carregar a sua sessão. Recarregue a página.
        </p>
      )}

      {(results.length > 0 || loading) && (
        <section
          className="search-results"
          aria-labelledby="search-results-title"
        >
          <h2 id="search-results-title" className="section-title">
            Resultado da busca
          </h2>
          <ul className="list">
            {results.map((result, i) => (
              <ResultItem key={result.normalized_name || i} result={result} />
            ))}
            {pendingNames.map((name, i) => (
              <li key={`pending-${i}`} className="search-result">
                <span className="search-result-name search-result-pending">
                  {name}
                </span>
                <span className="search-result-status muted">
                  Buscando nas listas…
                </span>
              </li>
            ))}
          </ul>
          <p role="status" className="visually-hidden">
            {loading ? "Buscando nas listas…" : "Busca concluída."}
          </p>
        </section>
      )}

      <Toast message={error} onClose={clearError} />
    </main>
  );
}
