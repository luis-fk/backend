"use client";

import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { logger } from "@/app/api/log/client-logger";
import { SavedAdmissionResult, ClassRoom, ResultChanges } from "@/cfflch/types";
import ResultCard from "@/cfflch/components/result-card";
import Toast from "@/app/components/Toast";
import "@/cfflch/css/results.css";

interface ResultsTableProps {
  serverUrl: string | undefined;
}

type PdfFilter = "all" | "found" | "not-found";

const PDF_FILTERS: { value: PdfFilter; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "found", label: "Com PDF" },
  { value: "not-found", label: "Sem PDF" },
];

function countLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

export default function ResultsTable({
  serverUrl,
}: ResultsTableProps): React.ReactElement {
  const [currentYear] = useState(() => new Date().getFullYear());
  const years = Array.from(
    { length: currentYear - 2000 + 1 },
    (_, i) => currentYear - i,
  );
  const [year, setYear] = useState(currentYear);
  const [results, setResults] = useState<SavedAdmissionResult[]>([]);
  // Last finished request; loading and failure are derived from it.
  const [loaded, setLoaded] = useState<{
    year: number;
    failed: boolean;
  } | null>(null);
  const [classrooms, setClassrooms] = useState<ClassRoom[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pdfFilter, setPdfFilter] = useState<PdfFilter>("all");
  const [classFilter, setClassFilter] = useState<number | null>(null);

  const loading = Boolean(serverUrl) && loaded?.year !== year;
  const failed = loaded?.year === year && loaded.failed;

  useEffect(() => {
    if (!serverUrl) return;

    const controller = new AbortController();
    axios
      .get<ClassRoom[]>(`${serverUrl}/api/cfflch/class-rooms/`, {
        signal: controller.signal,
      })
      .then((res) => setClassrooms(res.data))
      .catch((err: unknown) => {
        if (axios.isCancel(err)) return;
        logger.error("Failed to fetch classrooms", { error: err });
        setError("Não foi possível carregar as turmas. Tente de novo.");
      });

    return () => controller.abort();
  }, [serverUrl]);

  useEffect(() => {
    if (!serverUrl) return;

    const controller = new AbortController();
    axios
      .get<SavedAdmissionResult[]>(
        `${serverUrl}/api/cfflch/admission-results/`,
        { params: { year }, signal: controller.signal },
      )
      .then((res) => {
        setResults(res.data);
        setLoaded({ year, failed: false });
      })
      .catch((err: unknown) => {
        if (axios.isCancel(err)) return;
        logger.error("Failed to fetch admission results", {
          year,
          error: err,
        });
        setError("Não foi possível carregar os resultados. Tente de novo.");
        setLoaded({ year, failed: true });
      });

    return () => controller.abort();
  }, [serverUrl, year]);

  const handleDeleted = useCallback((id: number): void => {
    setResults((prev) => prev.filter((r) => r.id !== id));
  }, []);

  // A row saved a change: update it here too, so the summary and the class filter stay current.
  const handleUpdated = useCallback(
    (id: number, changes: ResultChanges): void => {
      setResults((prev) =>
        prev.map((r) => (r.id === id ? { ...r, ...changes } : r)),
      );
    },
    [],
  );

  const filtered = results
    .filter((r) => {
      if (pdfFilter === "all") return true;
      const hasPdf = (r.pdf_urls ?? []).length > 0;
      return pdfFilter === "found" ? hasPdf : !hasPdf;
    })
    .filter((r) =>
      classFilter === null ? true : r.class_room_id === classFilter,
    );

  // Counts the rows on screen. While a year loads or after it fails, results still hold
  // the previous year, so the summary stays empty.
  const approvedCount = filtered.filter((r) => r.approved).length;
  const summary =
    loading || failed
      ? null
      : `${countLabel(filtered.length, "aluno", "alunos")}, ${countLabel(approvedCount, "aprovado", "aprovados")}`;

  return (
    <main className="page">
      <div className="page-header">
        <h1 className="page-title">Resultados</h1>
        <p className="muted results-summary">{summary}</p>
      </div>

      <div className="results-toolbar">
        <div className="field">
          <label htmlFor="year-input" className="field-label">
            Ano
          </label>
          <select
            id="year-input"
            className="select"
            value={year}
            disabled={loading}
            onChange={(e) => {
              setYear(Number(e.target.value));
              setError(null);
            }}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <span id="pdf-filter-label" className="field-label">
            Listas
          </span>
          <div
            className="segmented"
            role="group"
            aria-labelledby="pdf-filter-label"
          >
            {PDF_FILTERS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={pdfFilter === option.value}
                onClick={() => setPdfFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label htmlFor="class-filter" className="field-label">
            Turma
          </label>
          <select
            id="class-filter"
            className="select"
            value={classFilter ?? ""}
            onChange={(e) =>
              setClassFilter(
                e.target.value === "" ? null : Number(e.target.value),
              )
            }
          >
            <option value="">Todas as turmas</option>
            {classrooms.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <p className="muted">Carregando resultados…</p>
      ) : failed ? (
        <p className="muted">
          Não foi possível carregar os resultados de {year}.
        </p>
      ) : filtered.length === 0 ? (
        <p className="muted">Nenhum resultado para {year}.</p>
      ) : (
        <ul className="list">
          {filtered.map((result) => (
            <ResultCard
              key={result.id}
              result={result}
              serverUrl={serverUrl}
              classrooms={classrooms}
              onDeleted={handleDeleted}
              onUpdated={handleUpdated}
            />
          ))}
        </ul>
      )}

      <Toast message={error} onClose={() => setError(null)} />
    </main>
  );
}
