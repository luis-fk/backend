"use client";

import { useState, useCallback } from "react";
import {
  useAdmissionSearch,
  AdmissionResult,
} from "@/cfflch/hooks/use-admission-search";
import Toast from "@/app/components/Toast";
import "@/cfflch/css/search.css";

function ResultItem({ result }: { result: AdmissionResult }): React.ReactElement {
  return (
    <div className="result-card">
      <div className="result-card-name">{result.student_name}</div>
      {result.pdf_entries.length > 0 ? (
        <div className="pdf-links">
          {result.pdf_entries.map((pdf) => (
            <a key={pdf.url} href={pdf.url} target="_blank" rel="noopener noreferrer">
              {pdf.search_title}
            </a>
          ))}
        </div>
      ) : (
        <span className="not-found">Not found in any PDF</span>
      )}
    </div>
  );
}

export default function SearchForm(): React.ReactElement {
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;
  const { results, loading, error, search, clearError } =
    useAdmissionSearch(serverUrl);

  const [namesValue, setNamesValue] = useState("");
  const [currentYear] = useState(() => new Date().getFullYear());
  const years = Array.from(
    { length: currentYear - 2000 + 1 },
    (_, i) => currentYear - i,
  );
  const [year, setYear] = useState(currentYear);
  const [className, setClassName] = useState("");

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault();
      const names = namesValue
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      if (names.length === 0) return;

      await search({
        names,
        year,
        ...(className.trim() ? { class_name: className.trim() } : {}),
      });
    },
    [namesValue, year, className, search],
  );

  return (
    <div className="search-container">
      <h1>Admission Search</h1>

      <form className="search-form" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="names">Student names (one per line)</label>
          <textarea
            id="names"
            value={namesValue}
            onChange={(e) => setNamesValue(e.target.value)}
            placeholder={"João Silva\nMaria Souza"}
            disabled={loading}
          />
        </div>
        <div>
          <label htmlFor="year">Year</label>
          <select
            id="year"
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
        <div>
          <label htmlFor="class-name">Class name (optional)</label>
          <input
            id="class-name"
            type="text"
            value={className}
            onChange={(e) => setClassName(e.target.value)}
            placeholder="Turma A"
            disabled={loading}
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {(results.length > 0 || loading) && (
        <div className="results-stream">
          <h2>Results</h2>
          {results.map((result, i) => (
            <ResultItem key={result.normalized_name || i} result={result} />
          ))}
          {loading && (
            <span className="loading-indicator">Waiting for more results...</span>
          )}
        </div>
      )}

      <Toast message={error} onClose={clearError} />
    </div>
  );
}