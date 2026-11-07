"use client";

import { useState, useCallback } from "react";
import axios from "axios";
import { logger } from "@/app/api/log/client-logger";
import { SavedAdmissionResult, PdfUrl, ClassRoom } from "@/cfflch/types";
import Toast from "@/app/components/Toast";

interface ResultCardProps {
  result: SavedAdmissionResult;
  serverUrl: string | undefined;
  classrooms: ClassRoom[];
  onDeleted: (id: number) => void;
}

export default function ResultCard({
  result,
  serverUrl,
  classrooms,
  onDeleted,
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
    } catch (err) {
      logger.error("Failed to update approved status", {
        id: result.id,
        error: err,
      });
      setApproved(previous);
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.error ?? "Failed to update. Please try again.",
        );
      } else {
        setError("Failed to update. Please try again.");
      }
    }
  }, [approved, result.id, serverUrl]);

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
      } catch (err) {
        logger.error("Failed to update class room", {
          id: result.id,
          error: err,
        });
        setClassRoomId(prev);
        if (axios.isAxiosError(err)) {
          setError(
            err.response?.data?.error ?? "Failed to update class. Please try again.",
          );
        } else {
          setError("Failed to update class. Please try again.");
        }
      }
    },
    [classRoomId, result.id, serverUrl],
  );

  const handleDelete = useCallback(async (): Promise<void> => {
    if (!serverUrl) return;
    if (!confirm(`Delete result for "${result.student_name}"?`)) return;

    try {
      await axios.delete(
        `${serverUrl}/api/cfflch/admission-results/${result.id}/`,
      );
      onDeleted(result.id);
    } catch (err) {
      logger.error("Failed to delete result", { id: result.id, error: err });
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.error ?? "Failed to delete. Please try again.",
        );
      } else {
        setError("Failed to delete. Please try again.");
      }
    }
  }, [result.id, result.student_name, serverUrl, onDeleted]);

  return (
    <div className="result-card">
      <div className="result-card-header">
        <span className="result-card-name">{result.student_name}</span>
        <div className="result-card-actions">
          <label className="approved-label">
            <input
              type="checkbox"
              checked={approved}
              onChange={handleApprovedToggle}
            />
            Approved
          </label>
          <select
            className="class-select"
            value={classRoomId ?? ""}
            onChange={handleClassChange}
          >
            <option value="">None</option>
            {classrooms.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button className="delete-button" onClick={handleDelete}>
            Delete
          </button>
        </div>
      </div>

      {(result.pdf_urls ?? []).length > 0 ? (
        <div className="pdf-links">
          {(result.pdf_urls ?? []).map((pdf: PdfUrl) => (
            <a key={pdf.url} href={pdf.url} target="_blank" rel="noopener noreferrer">
              {pdf.search_title}
            </a>
          ))}
        </div>
      ) : (
        <span className="not-found">Not found in any PDF</span>
      )}

      <Toast message={error} onClose={() => setError(null)} />
    </div>
  );
}