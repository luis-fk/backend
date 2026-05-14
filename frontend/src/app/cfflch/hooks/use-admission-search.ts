"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import axios from "axios";
import { logger } from "@/app/api/log/client-logger";

export type PdfEntry = { url: string; search_title: string };

export type AdmissionResult = {
  student_name: string;
  normalized_name: string;
  found: boolean;
  pdf_entries: PdfEntry[];
};

type WsItem = {
  student_name: string;
  normalized_name: string;
  year_found: number;
  search_query: string;
  pdf_url: string;
  search_title: string;
  found: boolean;
};

type WsDoneSignal = { done: true };
type WsMessage = WsItem[] | WsDoneSignal;

export type SearchParams = {
  names: string[];
  year: number;
  class_name?: string;
};

export function useAdmissionSearch(serverUrl: string | undefined): {
  results: AdmissionResult[];
  loading: boolean;
  error: string | null;
  search: (params: SearchParams) => Promise<void>;
  clearError: () => void;
} {
  const [results, setResults] = useState<AdmissionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const search = useCallback(
    async (params: SearchParams): Promise<void> => {
      if (!serverUrl) return;

      wsRef.current?.close();
      setResults([]);
      setLoading(true);
      setError(null);

      const requestId = crypto.randomUUID();

      const wsProtocol = serverUrl.startsWith("https://") ? "wss://" : "ws://";
      const wsHost = serverUrl.split("://")[1].replace(/\/$/, "");
      const wsUrl = `${wsProtocol}${wsHost}/ws/cfflch/admission-status/${requestId}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        logger.log("cfflch WebSocket connected", { requestId });
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: WsMessage = JSON.parse(event.data as string);
          if ("done" in msg) {
            setLoading(false);
            ws.close();
            return;
          }
          setResults((prev) => {
            const updated = [...prev];
            for (const item of msg) {
              const dedupeKey = item.normalized_name || item.student_name;
              const idx = updated.findIndex(
                (r) => (r.normalized_name || r.student_name) === dedupeKey,
              );
              if (idx !== -1) {
                if (item.found && item.pdf_url) {
                  updated[idx] = {
                    ...updated[idx],
                    found: true,
                    pdf_entries: [
                      ...updated[idx].pdf_entries,
                      { url: item.pdf_url, search_title: item.search_title },
                    ],
                  };
                }
              } else {
                updated.push({
                  student_name: item.student_name,
                  normalized_name: item.normalized_name || item.student_name,
                  found: item.found,
                  pdf_entries:
                    item.found && item.pdf_url
                      ? [{ url: item.pdf_url, search_title: item.search_title }]
                      : [],
                });
              }
            }
            return updated;
          });
        } catch (e) {
          logger.error("Failed to parse cfflch WebSocket message", {
            data: event.data,
            error: e,
          });
        }
      };

      ws.onerror = (event: Event) => {
        logger.error("cfflch WebSocket error", { requestId, event });
        setError("WebSocket connection error. Please try again.");
        setLoading(false);
      };

      ws.onclose = () => {
        logger.log("cfflch WebSocket closed", { requestId });
        setLoading(false);
      };

      await new Promise<void>((resolve) => {
        if (ws.readyState === WebSocket.OPEN) {
          resolve();
          return;
        }
        const originalOnOpen = ws.onopen;
        ws.onopen = (event) => {
          if (originalOnOpen) {
            (originalOnOpen as (event: Event) => void)(event);
          }
          resolve();
        };
      });

      try {
        await axios.post(`${serverUrl}/api/cfflch/admission-status/`, {
          names: params.names,
          year: params.year,
          request_id: requestId,
          ...(params.class_name ? { class_name: params.class_name } : {}),
        });
      } catch (err) {
        logger.error("cfflch POST failed", { error: err });
        if (axios.isAxiosError(err)) {
          setError(
            err.response?.data?.error ?? "Failed to start search. Please try again.",
          );
        } else {
          setError("Failed to start search. Please try again.");
        }
        setLoading(false);
        ws.close();
      }
    },
    [serverUrl],
  );

  return {
    results,
    loading,
    error,
    search,
    clearError: () => setError(null),
  };
}