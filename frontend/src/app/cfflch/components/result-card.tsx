"use client";

import { useState, useCallback } from "react";
import axios from "axios";
import { logger } from "@/app/api/log/client-logger";
import { SavedAdmissionResult, ClassRoom, ResultChanges } from "@/cfflch/types";
import Toast from "@/app/components/Toast";

interface ResultCardProps {
  result: SavedAdmissionResult;
  serverUrl: string | undefined;
  classrooms: ClassRoom[];
  onDeleted: (id: number) => void;
  onUpdated: (id: number, changes: ResultChanges) => void;
}

export default function ResultCard({
  result,
  serverUrl,
  classrooms,
  onDeleted,
  onUpdated,
}: ResultCardProps): React.ReactElement {
  const [approved, setApproved] = useState(result.approved);
  const [classRoomId, setClassRoomId] = useState(result.class_room_id);
  const [error, setError] = useState<string | null>(null);

  const handleApprovedToggle = useCallback(async (): Promise<void> => {
    if (!serverUrl) return;
    const previous = approved;
    setApproved(!previous);

    try {
      await axios.patch(
        `${serverUrl}/api/cfflch/admission-results/${result.id}/`,
        { approved: !previous },
      );
      onUpdated(result.id, { approved: !previous });
    } catch (err) {
      logger.error("Failed to update approved status", {
        id: result.id,
        error: err,
      });
      setApproved(previous);
      setError("Não foi possível atualizar a aprovação. Tente de novo.");
    }
  }, [approved, result.id, serverUrl, onUpdated]);

  const handleClassChange = useCallback(
    async (e: React.ChangeEvent<HTMLSelectElement>): Promise<void> => {
      if (!serverUrl) return;
      const newId = e.target.value === "" ? null : Number(e.target.value);
      const prev = classRoomId;
      setClassRoomId(newId);

      try {
        await axios.patch(
          `${serverUrl}/api/cfflch/admission-results/${result.id}/`,
          { class_room_id: newId },
        );
        onUpdated(result.id, { class_room_id: newId });
      } catch (err) {
        logger.error("Failed to update class room", {
          id: result.id,
          error: err,
        });
        setClassRoomId(prev);
        setError("Não foi possível mudar a turma. Tente de novo.");
      }
    },
    [classRoomId, result.id, serverUrl, onUpdated],
  );

  const handleDelete = useCallback(async (): Promise<void> => {
    if (!serverUrl) return;
    if (!confirm(`Excluir o resultado de ${result.student_name}?`)) return;

    try {
      await axios.delete(
        `${serverUrl}/api/cfflch/admission-results/${result.id}/`,
      );
      onDeleted(result.id);
    } catch (err) {
      logger.error("Failed to delete result", { id: result.id, error: err });
      setError("Não foi possível excluir o resultado. Tente de novo.");
    }
  }, [result.id, result.student_name, serverUrl, onDeleted]);

  const pdfUrls = result.pdf_urls ?? [];

  return (
    <li className="result-row">
      <div className="result-main">
        <span className="result-name">{result.student_name}</span>
        {pdfUrls.length > 0 ? (
          pdfUrls.map((pdf) => (
            <a
              key={pdf.url}
              className="result-link"
              href={pdf.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {pdf.search_title}
            </a>
          ))
        ) : (
          <span className="result-missing muted">
            Não aparece em nenhuma lista
          </span>
        )}
      </div>

      <div className="result-actions">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={approved}
            onChange={handleApprovedToggle}
          />
          Aprovado
        </label>
        <select
          className="select select-compact"
          aria-label={`Turma de ${result.student_name}`}
          value={classRoomId ?? ""}
          onChange={handleClassChange}
        >
          <option value="">Sem turma</option>
          {classrooms.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="text-button text-button-danger"
          onClick={handleDelete}
        >
          Excluir
        </button>
      </div>

      <Toast message={error} onClose={() => setError(null)} />
    </li>
  );
}
