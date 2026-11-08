"use client";

import { useEffect, useEffectEvent } from "react";

type Severity = "error" | "warning" | "info" | "success";

interface ToastProps {
  message: string | null;
  onClose: () => void;
  severity?: Severity;
}

const AUTO_HIDE_MS = 5000;

export default function Toast({
  message,
  onClose,
  severity = "error",
}: ToastProps): React.ReactElement | null {
  // Callers pass a new onClose on every render; reading it through an effect
  // event keeps the timer from restarting each time the parent re-renders.
  const close = useEffectEvent(() => onClose());

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(close, AUTO_HIDE_MS);
    return () => clearTimeout(timer);
  }, [message]);

  if (!message) return null;

  return (
    <div
      className="toast"
      data-severity={severity}
      role={severity === "error" ? "alert" : "status"}
    >
      <span className="dot" aria-hidden="true" />
      <span className="toast-message">{message}</span>
      <button
        type="button"
        className="toast-close"
        onClick={onClose}
        aria-label="Fechar aviso"
      >
        <svg
          aria-hidden="true"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
        >
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </div>
  );
}
