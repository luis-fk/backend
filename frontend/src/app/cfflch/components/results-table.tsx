"use client";

import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { logger } from "@/app/api/log/client-logger";
import { SavedAdmissionResult, ClassRoom } from "@/cfflch/types";
import ResultCard from "@/cfflch/components/result-card";
import Toast from "@/app/components/Toast";
import "@/cfflch/css/results.css";

interface ResultsTableProps {
  serverUrl: string | undefined;
}

type PdfFilter = "all" | "found" | "not-found";

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
  const [classrooms, setClassrooms] = useState<ClassRoom[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfFilter, setPdfFilter] = useState<PdfFilter>("all");
  const [classFilter, setClassFilter] = useState<number | null>(null);

  const fetchClassrooms = useCallback(async (): Promise<void> => {
    if (!serverUrl) return;
    try {
      const res = await axios.get<ClassRoom[]>(
        `${serverUrl}/api/cfflch/class-rooms/`,
      );
      setClassrooms(res.data);
    } catch (err) {
      logger.error("Failed to fetch classrooms", { error: err });
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.error ??
            "Failed to load classrooms. Please try again.",
        );
      } else {
        setError("Failed to load classrooms. Please try again.");
      }
    }
  }, [serverUrl]);

  const fetchResults = useCallback(
    async (selectedYear: number, signal: AbortSignal): Promise<void> => {
      if (!serverUrl) return;
      setLoading(true);
      setError(null);

      try {
        const res = await axios.get<SavedAdmissionResult[]>(
          `${serverUrl}/api/cfflch/admission-results/`,
          { params: { year: selectedYear }, signal },
        );
        setResults(res.data);
      } catch (err) {
        if (axios.isCancel(err)) return;
        logger.error("Failed to fetch admission results", {
          year: selectedYear,
          error: err,
        });
        if (axios.isAxiosError(err)) {
          setError(
            err.response?.data?.error ??
              "Failed to load results. Please try again.",
          );
        } else {
          setError("Failed to load results. Please try again.");
        }
      } finally {
        setLoading(false);
      }
    },
    [serverUrl],
  );

  useEffect(() => {
    fetchClassrooms();
  }, [fetchClassrooms]);

  useEffect(() => {
    const controller = new AbortController();
    fetchResults(year, controller.signal);
    return () => controller.abort();
  }, [year, fetchResults]);

  const handleDeleted = useCallback((id: number): void => {
    setResults((prev) => prev.filter((r) => r.id !== id));
  }, []);

  const filtered = results
    .filter((r) => {
      if (pdfFilter === "all") return true;
      const hasPdf = (r.pdf_urls ?? []).length > 0;
      return pdfFilter === "found" ? hasPdf : !hasPdf;
    })
    .filter((r) =>
      classFilter === null ? true : r.class_room_id === classFilter,
    );

  return (
    <div className="results-container">
      <h1>Admission Results</h1>

      <div className="year-selector">
        <label htmlFor="year-input">Year</label>
        <select
          id="year-input"
          value={year}
          disabled={loading}
          onChange={(e) => setYear(Number(e.target.value))}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-row">
        <div className="filter-group">
          <label htmlFor="pdf-filter">PDF</label>
          <select
            id="pdf-filter"
            value={pdfFilter}
            onChange={(e) => setPdfFilter(e.target.value as PdfFilter)}
          >
            <option value="all">All</option>
            <option value="found">Found</option>
            <option value="not-found">Not found</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="class-filter">Class</label>
          <select
            id="class-filter"
            value={classFilter ?? ""}
            onChange={(e) =>
              setClassFilter(e.target.value === "" ? null : Number(e.target.value))
            }
          >
            <option value="">All classes</option>
            {classrooms.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <span className="loading-state">Loading results...</span>
      ) : filtered.length === 0 ? (
        <span className="empty-state">No results found for {year}.</span>
      ) : (
        <div className="results-list">
          {filtered.map((result) => (
            <ResultCard
              key={result.id}
              result={result}
              serverUrl={serverUrl}
              classrooms={classrooms}
              onDeleted={handleDeleted}
            />
          ))}
        </div>
      )}

      <Toast message={error} onClose={() => setError(null)} />
    </div>
  );
}