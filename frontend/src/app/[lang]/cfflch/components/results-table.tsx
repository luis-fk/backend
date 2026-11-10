"use client";

import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { logger } from "@/app/api/log/client-logger";
import { SavedAdmissionResult, ClassRoom, ResultChanges } from "@/cfflch/types";
import ResultCard from "@/cfflch/components/result-card";
import Toast from "@/app/components/Toast";
import { commonDictionary } from "@/app/dictionary";
import type { Locale } from "@/app/i18n";
import { useLocale } from "@/app/useLocale";
import "@/cfflch/css/results.css";
import { errorMessage } from "@/cfflch/api-errors";
import { cfflchDictionary } from "@/cfflch/dictionary";

interface ResultsTableProps {
  serverUrl: string | undefined;
}

type PdfFilter = "all" | "found" | "not-found";

// Their labels are the dictionary's pdfFilters.
const PDF_FILTERS: readonly PdfFilter[] = ["all", "found", "not-found"];

// "3 alunos": the number in the page's language, and the word the dictionary
// gives for that count, since each language has its own plural.
function countLabel(
  count: number,
  word: (count: number) => string,
  lang: Locale,
): string {
  return `${count.toLocaleString(lang)} ${word(count)}`;
}

export default function ResultsTable({
  serverUrl,
}: ResultsTableProps): React.ReactElement {
  const lang = useLocale();
  const t = cfflchDictionary[lang].results;
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

  const session = useSession("cfflch");
  const token = session?.token;

  const loading = Boolean(serverUrl) && loaded?.year !== year;
  const failed = loaded?.year === year && loaded.failed;

  useEffect(() => {
    if (!serverUrl || !token) return;

    const controller = new AbortController();
    axios
      .get<ClassRoom[]>(`${serverUrl}/api/cfflch/class-rooms/`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })
      .then((res) => setClassrooms(res.data))
      .catch((err: unknown) => {
        if (axios.isCancel(err)) return;
        logger.error("Failed to fetch classrooms", { error: err });
        setError(errorMessage(lang, err, t.classesError));
      });

    return () => controller.abort();
  }, [serverUrl, token, lang, t]);

  useEffect(() => {
    if (!serverUrl || !token) return;

    const controller = new AbortController();
    axios
      .get<SavedAdmissionResult[]>(
        `${serverUrl}/api/cfflch/admission-results/`,
        {
          headers: { Authorization: `Bearer ${token}` },
          params: { year },
          signal: controller.signal,
        },
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
        setError(errorMessage(lang, err, t.resultsError));
        setLoaded({ year, failed: true });
      });

    return () => controller.abort();
  }, [serverUrl, token, year, lang, t]);

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

  // Counts the rows on screen. While a year loads, after it fails, or when nothing
  // is on screen (the empty message says why), the summary stays empty.
  const approvedCount = filtered.filter((r) => r.approved).length;
  const summary =
    loading || failed || filtered.length === 0
      ? null
      : `${countLabel(filtered.length, t.summary.students, lang)}, ${countLabel(approvedCount, t.summary.approved, lang)}`;

  return (
    <main className="page">
      <div className="page-header">
        <h1 className="page-title">{t.title}</h1>
        <p className="muted results-summary">{summary}</p>
      </div>

      <div className="results-toolbar">
        <div className="field">
          <label htmlFor="year-input" className="field-label">
            {t.yearLabel}
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
            {t.listsLabel}
          </span>
          <div
            className="segmented"
            role="group"
            aria-labelledby="pdf-filter-label"
          >
            {PDF_FILTERS.map((filter) => (
              <button
                key={filter}
                type="button"
                aria-pressed={pdfFilter === filter}
                onClick={() => setPdfFilter(filter)}
              >
                {t.pdfFilters[filter]}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label htmlFor="class-filter" className="field-label">
            {t.classLabel}
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
            <option value="">{t.allClasses}</option>
            {classrooms.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {session === null ? (
        <p className="muted">{commonDictionary[lang].session.loadFailed}</p>
      ) : loading ? (
        <p className="muted">{t.loading}</p>
      ) : failed ? (
        <p className="muted">{t.failed(year)}</p>
      ) : results.length === 0 ? (
        <p className="muted">{t.empty(year)}</p>
      ) : filtered.length === 0 ? (
        <p className="muted">{t.noMatches}</p>
      ) : (
        <ul className="list">
          {filtered.map((result) => (
            <ResultCard
              key={result.id}
              result={result}
              serverUrl={serverUrl}
              token={token}
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
